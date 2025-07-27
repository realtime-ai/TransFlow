import objc
from Foundation import NSObject, NSRunLoop, NSDate
from AVFoundation import AVAudioFormat, AVAudioConverter
from ScreenCaptureKit import (
    SCShareableContent,
    SCContentFilter,
    SCStreamConfiguration,
    SCStream,
    SCStreamOutputTypeAudio
)
import threading
import queue
import wave
import struct
import numpy as np

# 用于保存音频数据的队列
pcm_queue = queue.Queue()

class CaptureDelegate(NSObject):
    """SCStreamDelegate 的 Python 实现，用于接收音频样本。"""
    def init(self):
        self = objc.super(CaptureDelegate, self).init()
        return self

    # 回调方法：处理音频缓冲区
    def stream_didOutputSampleBuffer_ofType_(self, stream, sampleBuffer, bufferType):
        # 只处理音频
        if bufferType != SCStreamOutputTypeAudio:
            return

        try:
            # 简单地保存原始音频数据
            # 这里我们假设音频格式是 48kHz, 2通道, 32位浮点
            # 实际应用中应该从 formatDescription 获取格式信息
            
            # 导入需要的 Core Media 函数
            from CoreMedia import (
                CMSampleBufferGetDataBuffer,
                CMBlockBufferGetDataLength,
                CMBlockBufferGetDataPointer
            )
            
            # 获取音频数据的 CMBlockBuffer
            dataBuffer = CMSampleBufferGetDataBuffer(sampleBuffer)
            if not dataBuffer:
                return
                
            # 获取数据长度
            length = CMBlockBufferGetDataLength(dataBuffer)
            if length == 0:
                return
            
            # 获取数据指针并读取数据
            # PyObjC 处理 CMBlockBuffer 的方式
            # CMBlockBufferGetDataPointer returns (err, lengthAtOffset, totalLength, dataPointer)
            result = CMBlockBufferGetDataPointer(
                dataBuffer, 0, None, None, None
            )
            
            if isinstance(result, tuple) and len(result) >= 4:
                err = result[0]
                # The data pointer is in a tuple at index 3
                data_pointer_info = result[3]
                if isinstance(data_pointer_info, tuple) and len(data_pointer_info) > 0:
                    # The actual pointer is the first element
                    data_pointer = data_pointer_info[0]
                else:
                    data_pointer = None
            else:
                print(f"Unexpected result from CMBlockBufferGetDataPointer: {result}")
                return
            
            if err == 0 and data_pointer and length > 0:
                # Create a buffer from the pointer address
                import ctypes
                # Cast the integer address to a pointer and create a buffer
                buffer = (ctypes.c_char * length).from_address(data_pointer)
                raw_data = bytes(buffer)
                
                # 假设输入是 32 位浮点，转换为 16 位整数
                # 解析浮点数据
                float_data = struct.unpack(f'{length//4}f', raw_data)
                
                # 转换为 16 位整数
                int_data = np.array(float_data) * 32767
                int_data = np.clip(int_data, -32768, 32767).astype(np.int16)
                
                # 存入队列
                pcm_queue.put(int_data.tobytes())
                
        except Exception as e:
            print(f"处理音频时出错: {e}")
            import traceback
            traceback.print_exc()


def list_displays_and_apps():
    """列出可捕获的显示器和运行中的应用"""
    # SCShareableContent 需要异步获取,这里创建一个同步封装
    content_ref = [None]
    semaphore = threading.Semaphore(0)
    
    def completion_handler(content, error):
        if error:
            print(f"Error getting shareable content: {error}")
        content_ref[0] = content
        semaphore.release()
    
    # 异步获取可共享内容
    SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, completion_handler
    )
    
    # 等待结果
    semaphore.acquire()
    content = content_ref[0]
    
    if content is None:
        return [], []
    
    displays = content.displays() if hasattr(content, 'displays') else []
    apps = content.applications() if hasattr(content, 'applications') else []
    return displays, apps


def record_system_audio(duration_seconds=10, output_path="system_audio.wav"):
    """录制系统所有应用的声音到 WAV 文件"""
    displays, _ = list_displays_and_apps()
    if not displays:
        raise RuntimeError("未找到可用显示器")

    # 选择主显示器并不过滤任何应用:contentReference[oaicite:9]{index=9}
    display = displays[0]
    filter = SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(display, [], [])

    # 配置流：启用音频并排除当前进程的声音
    config = SCStreamConfiguration.alloc().init()
    config.setCapturesAudio_(True)
    config.setExcludesCurrentProcessAudio_(True)

    # 创建流并添加音频输出
    delegate = CaptureDelegate.alloc().init()
    stream = SCStream.alloc().initWithFilter_configuration_delegate_(filter, config, delegate)
    # Use None for queue to use default queue
    success, err = stream.addStreamOutput_type_sampleHandlerQueue_error_(delegate, SCStreamOutputTypeAudio, None, None)
    if not success:
        raise RuntimeError(f"添加流输出失败: {err}")

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

    print(f"开始录制 {duration_seconds} 秒...\n")
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
    
    print("录制结束，正在写入文件...")

    # 将队列中的音频数据写入 WAV
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(2)  # 立体声
        wf.setsampwidth(2)  # 16 位
        wf.setframerate(48000)  # Standard audio sample rate
        while not pcm_queue.empty():
            wf.writeframes(pcm_queue.get())

    print(f"音频已保存到 {output_path}")


if __name__ == '__main__':
    record_system_audio(5, "system_audio.wav")
