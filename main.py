from pickle import TRUE
import objc
import time

from Foundation import NSObject, NSRunLoop, NSDate
from AVFoundation import AVCaptureDevice, AVMediaTypeAudio
from ScreenCaptureKit import (
    SCShareableContent,
    SCContentFilter,
    SCStreamConfiguration,
    SCStream,
    SCStreamOutputTypeAudio,
    SCStreamOutputTypeMicrophone
)


import threading
import queue
import numpy as np
import soundfile as sf
from backend.audio.resampler import AudioResampler

# 用于保存音频数据的队列
pcm_queue = queue.Queue()
mic_queue = queue.Queue()  # 用于保存麦克风音频数据

# 全局变量存储音频格式信息
audio_formats = {}

# 全局音频重采样器
system_resampler = None
mic_resampler = None

class CaptureDelegate(NSObject):
    """SCStreamDelegate 的 Python 实现，用于接收音频样本。"""
    def init(self):
        self = objc.super(CaptureDelegate, self).init()
        # 初始化统计信息
        self.recording_start_time = None
        self.first_packet_time = None
        self.last_packet_time = None
        self.packet_times = []
        return self

    # 回调方法：处理音频缓冲区
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, bufferType):
        # 处理不同类型的音频流
        if bufferType not in (SCStreamOutputTypeAudio, SCStreamOutputTypeMicrophone):
            return

        try:
            # 获取音频数据 - 使用更直接的方法
            from CoreMedia import (
                CMSampleBufferGetDataBuffer,
                CMSampleBufferGetNumSamples,
                CMBlockBufferGetDataLength,
                CMBlockBufferCopyDataBytes,
                CMSampleBufferGetFormatDescription,
                CMSampleBufferGetPresentationTimeStamp
            )
            from Foundation import NSMutableData



            # 获取音频格式描述并调试（仅记录一次）
            formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer)
            debug_attr = f"{bufferType}_format_logged"
            if formatDesc and not hasattr(self, debug_attr):
                try:
                    stream_name = "麦克风" if bufferType == SCStreamOutputTypeMicrophone else "系统音频"
                    print(f"[调试] {stream_name}音频格式描述对象: {formatDesc}")
                    setattr(self, debug_attr, True)
                except:
                    pass
            
            # 获取音频数据的 CMBlockBuffer
            dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer)
            if not dataBuffer:
                return

            # 获取时间戳
            current_time = time.time()
            
            # 记录时间统计
            if self.recording_start_time is None:
                self.recording_start_time = current_time
                self.first_packet_time = current_time
            
            self.last_packet_time = current_time
            self.packet_times.append(current_time)
            

            # 获取数据长度
            length = CMBlockBufferGetDataLength(dataBuffer)
            if length == 0:
                return
            
            # 使用CMBlockBufferCopyDataBytes获取数据，这是更安全的方法
            # 创建目标数据缓冲区
            destinationBuffer = NSMutableData.dataWithLength_(length)
            if not destinationBuffer:
                return
            
            # 复制数据
            result = CMBlockBufferCopyDataBytes(dataBuffer, 0, length, destinationBuffer.mutableBytes())
            
            # 处理CMBlockBufferCopyDataBytes的返回值
            error_code = 0
            if isinstance(result, tuple):
                error_code = result[0] if len(result) > 0 else 0
            else:
                error_code = result
            
            if error_code == 0:  # kCMBlockBufferNoErr
                # 获取Python bytes
                raw_data = destinationBuffer.bytes().tobytes()
                
                # 分析音频格式信息
                self._analyze_audio_format(sampleBuffer, bufferType, raw_data)
                
                
                # 添加调试信息
                if not hasattr(self, 'packet_count'):
                    self.packet_count = {}
                
                stream_key = "mic" if bufferType == SCStreamOutputTypeMicrophone else "system"
                if stream_key not in self.packet_count:
                    self.packet_count[stream_key] = 0
                
                self.packet_count[stream_key] += 1
                
                # 每50个包打印一次统计
                if self.packet_count[stream_key] % 50 == 0:
                    elapsed_time = current_time - self.recording_start_time
                    packets_per_second = self.packet_count[stream_key] / elapsed_time if elapsed_time > 0 else 0
                    print(f"[{stream_key}] 包#{self.packet_count[stream_key]}: {packets_per_second:.1f} 包/秒")
                
                if bufferType == SCStreamOutputTypeMicrophone:
                    mic_queue.put(raw_data)
                elif bufferType == SCStreamOutputTypeAudio:
                    pcm_queue.put(raw_data)
            else:
                print(f"Failed to copy audio data, error code: {error_code}")
                
        except Exception as e:
            print(f"处理音频时出错: {e}")
            import traceback
            traceback.print_exc()
    
    def _analyze_audio_format(self, sampleBuffer, bufferType, raw_data):
        """分析音频格式信息"""
        try:
            from CoreMedia import (
                CMSampleBufferGetFormatDescription,
                CMAudioFormatDescriptionGetStreamBasicDescription
            )
            
            # 确定流类型
            stream_type = "麦克风" if bufferType == SCStreamOutputTypeMicrophone else "系统音频"
            format_key = "microphone" if bufferType == SCStreamOutputTypeMicrophone else "system"
            
            # 初始化计数器
            if not hasattr(self, 'format_analyzed'):
                self.format_analyzed = {}
            
            # 每种类型只分析一次
            if stream_type not in self.format_analyzed:
                self.format_analyzed[stream_type] = True
                
                print(f"\n[音频格式分析] {stream_type}")
                
                # 获取格式描述
                formatDesc = CMSampleBufferGetFormatDescription(sampleBuffer)
                if formatDesc:

                    try:
                        # 使用Core Media API获取AudioStreamBasicDescription
                        asbd = CMAudioFormatDescriptionGetStreamBasicDescription(formatDesc)
                        if asbd:
                            # 直接访问AudioStreamBasicDescription结构体的字段
                            sample_rate = int(asbd.mSampleRate) if hasattr(asbd, 'mSampleRate') else 44100
                            channels = int(asbd.mChannelsPerFrame) if hasattr(asbd, 'mChannelsPerFrame') else 1
                            bit_depth = int(asbd.mBitsPerChannel) if hasattr(asbd, 'mBitsPerChannel') else 16
                            
                            # 更新全局格式信息
                            global audio_formats, system_resampler, mic_resampler
                            audio_formats[format_key] = {
                                'sample_rate': sample_rate,
                                'channels': channels,
                                'bit_depth': bit_depth
                            }
                            
                            print(f"[格式] {stream_type}: {sample_rate}Hz, {channels}声道, {bit_depth}位")
                            
                            # 创建对应的重采样器 - 统一转换为16kHz, 单声道, int16
                            target_format = 'flt' if bit_depth == 32 else 's16'
                            if format_key == 'system':
                                system_resampler = AudioResampler(
                                    input_sample_rate=sample_rate,
                                    output_sample_rate=16000,
                                    input_channels=channels,
                                    output_channels=1,
                                    input_format=target_format,
                                    output_format='s16'
                                )
                                print(f"[重采样器] 系统音频: {sample_rate}Hz/{channels}ch → 16kHz/1ch")
                            elif format_key == 'microphone':
                                mic_resampler = AudioResampler(
                                    input_sample_rate=sample_rate,
                                    output_sample_rate=16000,
                                    input_channels=channels,
                                    output_channels=1,
                                    input_format=target_format,
                                    output_format='s16'
                                )
                                print(f"[重采样器] 麦克风: {sample_rate}Hz/{channels}ch → 16kHz/1ch")
                    except Exception as parse_error:
                        print(f"格式解析失败: {parse_error}")
                
        except Exception as e:
            print(f"格式分析错误: {e}")

def get_displays():
    """获取可捕获的显示器"""
    content_ref = [None]
    semaphore = threading.Semaphore(0)
    
    def completion_handler(content, error):
        if error:
            print(f"Error getting shareable content: {error}")
        content_ref[0] = content
        semaphore.release()
    
    SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, completion_handler
    )
    
    semaphore.acquire()
    content = content_ref[0]
    
    if content is None:
        return []
    
    displays = content.displays() if hasattr(content, 'displays') else []
    return displays


def list_microphones():
    """列出可用的麦克风设备"""
    # 获取所有音频输入设备
    devices = AVCaptureDevice.devicesWithMediaType_(AVMediaTypeAudio)
    
    microphones = []
    for device in devices:
        mic_info = {
            'name': device.localizedName(),
            'unique_id': device.uniqueID(),
            'model_id': device.modelID(),
            'is_connected': device.isConnected(),
        }
        microphones.append(mic_info)
    
    return microphones


def record_system_audio(duration_seconds=10, output_path="system_audio.wav", 
                       capture_mic=True, mic_device_id=None,
                       sample_rate=16000, channels=1, bit_depth=16):
    """录制系统所有应用的声音到 WAV 文件
    
    Args:
        duration_seconds: 录制时长（秒）
        output_path: 输出文件路径
        capture_mic: 是否同时录制麦克风
        mic_device_id: 指定麦克风设备ID，None表示使用默认麦克风
        sample_rate: 采样率（默认16000 Hz）
        channels: 通道数（默认1，单声道）
        bit_depth: 位深度（默认16位）
    """
    # 清理旧的队列数据
    global pcm_queue, mic_queue
    cleared_count = 0
    while not pcm_queue.empty():
        pcm_queue.get()
        cleared_count += 1
    mic_cleared_count = 0
    while not mic_queue.empty():
        mic_queue.get()
        mic_cleared_count += 1
    print(f"[清理] 清理了 {cleared_count} 个系统音频队列项, {mic_cleared_count} 个麦克风队列项")
    # 获取麦克风设备
    if capture_mic:
        mics = list_microphones()
        if mics:
            if mic_device_id is None:
                mic_device_id = mics[0]['unique_id']
                print(f"使用默认麦克风: {mics[0]['name']}")
        else:
            print("未找到可用的麦克风设备")
            capture_mic = False
    
    displays = get_displays()
    if not displays:
        raise RuntimeError("未找到可用显示器")

    # 选择主显示器并不过滤任何应用
    display = displays[0]
    filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(display, [], [])

    # 配置流：启用音频并排除当前进程的声音
    config = SCStreamConfiguration.alloc().init()
    config.setCapturesAudio_(True)
    config.setExcludesCurrentProcessAudio_(True)
    
    # 不强制设置采样率，让系统使用默认值以避免重采样噪音
    # config.setSampleRate_(sample_rate)
    
    # 设置音频通道数为单声道
    config.setChannelCount_(channels)
    
    # 启用麦克风捕获
    if capture_mic:
        config.setCaptureMicrophone_(True)
        if mic_device_id:
            # 设置特定的麦克风设备
            config.setMicrophoneCaptureDeviceID_(mic_device_id)
    else:
        # 明确禁用麦克风捕获
        config.setCaptureMicrophone_(False)

    # 创建共用的音频委托
    delegate = CaptureDelegate.alloc().init()
    stream = SCStream.alloc().initWithFilter_configuration_delegate_(filter, config, delegate)
    
    # 添加系统音频输出
    success, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(delegate, SCStreamOutputTypeAudio, None, None)
    if not success:
        raise RuntimeError(f"添加系统音频流输出失败: {err}")
    
    # 如果启用麦克风捕获，添加麦克风输出（使用同一个委托）
    if capture_mic:
        success, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(delegate, SCStreamOutputTypeMicrophone, None, None)
        if not success:
            print(f"警告：添加麦克风流输出失败: {err}")
            print("将继续录制系统音频（混合模式）")


    # 启动捕获
    capture_started = [False]
    capture_error = [None]
    semaphore = threading.Semaphore(0)
    
    def start_handler(error):
        if error:
            capture_error[0] = error
        else:
            capture_started[0] = True
        semaphore.release()
    
    stream.startCaptureWithCompletionHandler_(start_handler)
    semaphore.acquire()
    
    if capture_error[0]:
        raise RuntimeError(f"启动捕获失败: {capture_error[0]}")
    
    if not capture_started[0]:
        raise RuntimeError("启动捕获失败")

    print(f"开始录制 {duration_seconds} 秒...")
    if capture_mic:
        print("同时录制系统音频和麦克风音频（分离模式）")
    else:
        print("仅录制系统音频")
    print()
    
    # 运行循环，持续指定时长
    end_time = NSDate.date().timeIntervalSince1970() + duration_seconds
    while NSDate.date().timeIntervalSince1970() < end_time:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    # 停止捕获
    stop_semaphore = threading.Semaphore(0)
    
    def stop_handler(error):
        if error:
            print(f"停止捕获时出错: {error}")
        stop_semaphore.release()
    
    stream.stopCaptureWithCompletionHandler_(stop_handler)
    stop_semaphore.acquire()
    
    # 等待一小段时间，确保所有缓冲的音频数据都处理完毕
    print("等待缓冲数据处理完毕...")
    import time
    time.sleep(0.1)  # 100ms 等待
    
    print(f"停止后队列大小: 系统音频={pcm_queue.qsize()}, 麦克风={mic_queue.qsize()}")
    
    print("录制结束，正在写入文件...")
    
    # 打印详细的包统计信息
    if hasattr(delegate, 'packet_count') and hasattr(delegate, 'recording_start_time'):
        total_recording_time = delegate.last_packet_time - delegate.recording_start_time if delegate.last_packet_time else 0
        system_packets = delegate.packet_count.get('system', 0)
        mic_packets = delegate.packet_count.get('mic', 0)
        
        print(f"\n=== 包统计分析 ===")
        print(f"录制设定时长: {duration_seconds} 秒")
        print(f"实际录制时长: {total_recording_time:.2f} 秒")
        print(f"系统音频包数: {system_packets}")
        print(f"麦克风包数: {mic_packets}")
        
        if system_packets > 0 and total_recording_time > 0:
            avg_packets_per_sec = system_packets / total_recording_time
            expected_packets_20ms = duration_seconds * 50  # 20ms间隔 = 50包/秒
            expected_packets_40ms = duration_seconds * 25  # 40ms间隔 = 25包/秒
            
            print(f"实际包频率: {avg_packets_per_sec:.1f} 包/秒")
            print(f"期望包频率(20ms): {expected_packets_20ms} 包 ({expected_packets_20ms/duration_seconds:.1f} 包/秒)")
            print(f"期望包频率(40ms): {expected_packets_40ms} 包 ({expected_packets_40ms/duration_seconds:.1f} 包/秒)")
            
            # 计算包间隔
            if len(delegate.packet_times) > 1:
                intervals = [delegate.packet_times[i] - delegate.packet_times[i-1] 
                           for i in range(1, min(11, len(delegate.packet_times)))]  # 只看前10个间隔
                avg_interval = sum(intervals) / len(intervals) * 1000  # 转换为毫秒
                print(f"前10个包的平均间隔: {avg_interval:.1f} ms")
        
        print("=" * 30)

    # 将队列中的音频数据写入 WAV
    # 保存系统音频（使用重采样器统一转换为16kHz, 单声道, int16）
    system_format = audio_formats['system']
    system_output_path = output_path.replace('.wav', '_system.wav') if capture_mic else output_path
    
    print(f"[保存] 系统音频重采样: {system_format['sample_rate']}Hz/{system_format['channels']}ch → 16kHz/1ch")
    
    # 收集所有音频数据并使用重采样器处理
    resampled_chunks = []
    packet_count = 0
    
    while not pcm_queue.empty():
        raw_data = pcm_queue.get()
        packet_count += 1
        
        if system_resampler:
            try:
                # 使用重采样器处理数据
                resampled_data, _ = system_resampler.resample(raw_data)
                if len(resampled_data) > 0:
                    resampled_chunks.append(resampled_data)
                    
                # 调试信息（只打印前5个包）
                if packet_count <= 5:
                    print(f"[重采样] 包#{packet_count}: {len(raw_data)}字节 -> {len(resampled_data)}样本")
                    
            except Exception as e:
                print(f"重采样失败 包#{packet_count}: {e}")
        else:
            print(f"警告: 系统音频重采样器未初始化")
    
    print(f"[调试] 总共处理了 {packet_count} 个数据包")
    
    # 合并重采样后的数据
    if resampled_chunks:
        final_audio_data = np.concatenate(resampled_chunks, axis=0)
        
        # 保存为16kHz, 单声道, int16
        sf.write(
            system_output_path, 
            final_audio_data, 
            16000,  # 固定16kHz
            subtype='PCM_16',  # 固定int16
            format='WAV'
        )
        
        total_samples = len(final_audio_data)
        actual_duration = total_samples / 16000  # 固定16kHz采样率
        
        print(f"系统音频已保存到 {system_output_path}")
        print(f"[统计] 系统音频: {total_samples} 样本, 实际时长: {actual_duration:.2f}秒 (16kHz, 单声道, int16)")
    else:
        print("警告: 没有系统音频数据可保存")
    
    # 保存麦克风音频（使用重采样器统一转换为16kHz, 单声道, int16）
    if capture_mic and not mic_queue.empty():
        mic_format = audio_formats['microphone']
        mic_output_path = output_path.replace('.wav', '_microphone.wav')
        
        print(f"[保存] 麦克风音频重采样: {mic_format['sample_rate']}Hz/{mic_format['channels']}ch → 16kHz/1ch")
        
        # 收集所有麦克风音频数据并使用重采样器处理
        mic_resampled_chunks = []
        mic_packet_count = 0
        
        while not mic_queue.empty():
            raw_data = mic_queue.get()
            mic_packet_count += 1
            
            if mic_resampler:
                try:
                    # 使用重采样器处理数据
                    resampled_data, _ = mic_resampler.resample(raw_data)
                    if len(resampled_data) > 0:
                        mic_resampled_chunks.append(resampled_data)
                        
                    # 调试信息（只打印前5个包）
                    if mic_packet_count <= 5:
                        print(f"[重采样] 麦克风包#{mic_packet_count}: {len(raw_data)}字节 -> {len(resampled_data)}样本")
                        
                except Exception as e:
                    print(f"麦克风重采样失败 包#{mic_packet_count}: {e}")
            else:
                print(f"警告: 麦克风重采样器未初始化")
        
        print(f"[调试] 麦克风总共处理了 {mic_packet_count} 个数据包")
        
        # 合并重采样后的麦克风数据
        if mic_resampled_chunks:
            final_mic_data = np.concatenate(mic_resampled_chunks, axis=0)
            
            # 保存为16kHz, 单声道, int16
            sf.write(
                mic_output_path, 
                final_mic_data, 
                16000,  # 固定16kHz
                subtype='PCM_16',  # 固定int16
                format='WAV'
            )
            
            total_mic_samples = len(final_mic_data)
            mic_actual_duration = total_mic_samples / 16000  # 固定16kHz采样率
            
            print(f"麦克风音频已保存到 {mic_output_path}")
            print(f"[统计] 麦克风音频: {total_mic_samples} 样本, 实际时长: {mic_actual_duration:.2f}秒 (16kHz, 单声道, int16)")
        else:
            print("警告: 没有麦克风音频数据可保存")
    elif capture_mic:
        print("未检测到麦克风音频数据")


def record_audio(duration_seconds=10, output_path="recording.wav", 
                capture_mic=True, mic_device_id=None,
                sample_rate=16000, channels=1, bit_depth=16):
    """录制音频功能
    
    Args:
        duration_seconds: 录制时长（秒）
        output_path: 输出文件路径
        capture_mic: 是否同时录制麦克风
        mic_device_id: 指定麦克风设备ID，None表示使用默认麦克风
        sample_rate: 采样率（默认16000 Hz）
        channels: 通道数（默认1，单声道）
        bit_depth: 位深度（默认16位）
    """
    # 直接调用录制函数
    record_system_audio(duration_seconds, output_path, capture_mic, mic_device_id,
                       sample_rate, channels, bit_depth)



if __name__ == '__main__':
    # 可以通过命令行参数选择不同的录制模式
    
    # 测试麦克风设备选择
    print("=== 获取可用麦克风设备 ===")
    mics = list_microphones()
    default_mic = None
    if mics:
        print("可用的麦克风设备:")
        for i, mic in enumerate(mics):
            print(f"  {i}: {mic['name']} (ID: {mic['unique_id']})")
            if 'macbook' in mic['name'].lower() or 'microphone' in mic['name'].lower():
                print(f"    -> 检测到内置麦克风: {mic['name']}")
                default_mic = mic
        
        # 选择默认内置麦克风（通常是第一个）
        default_mic = mics[0] if default_mic is None else default_mic
        print(f"\n使用默认麦克风进行测试: {default_mic['name']}")
        print(f"设备ID: {default_mic['unique_id']}")
        
        # 录制测试
        record_audio(10, "test_recording.wav", 
                    capture_mic=True,
                    mic_device_id=default_mic['unique_id'])
    else:
        print("未找到可用的麦克风设备")
    
    # 示例2：仅录制系统音频（16kHz, 单声道）
    # print("=== 仅录制系统音频（16kHz, 单声道） ===")
    # record_audio(5, "system_only_16k_mono.wav", 
    #             capture_mic=False,
    #             sample_rate=16000,
    #             channels=1,
    #             bit_depth=16)
    