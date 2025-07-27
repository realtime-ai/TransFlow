通过 SCShareableContent 获取可用显示器后，只需选择一个显示器并传入空的 excludingApplications 列表即可捕获该显示器上的所有应用和其音频


配置中启用了 capturesAudio 并设置 excludesCurrentProcessAudio = True，这样录制时不会出现脚本自身的输出声音


stream_didOutputSampleBuffer_ofType_ 回调仅处理类型为 .audio 的样本。由于音频数据默认是 32 位浮点格式，需要使用 AVAudioConverter 转换为 16 位整数以便保存为 WAV 文件


如果希望仅录制特定应用的声音，可使用运行中的应用列表构建 SCContentFilter。下面的函数展示了如何根据应用名称匹配 SCRunningApplication，然后创建只包含这些应用的过滤器并录制音频。

