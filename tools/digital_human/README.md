# Digital Human Tools

这个目录放本地数字人驱动引擎。

当前 Creator Studio 已经内置了一类正式接入：

- `SadTalker`

## 推荐接入顺序

1. 先准备一张正脸头像图，尽量单人、光线稳定、背景干净。
2. 运行 `install_sadtalker_workspace.ps1` 下载源码。
3. 如果你本机已经有兼容 Python，再加上 `-CreateVenv -InstallRequirements` 创建独立运行环境。
4. 如需自动拉取 release 资源，再加 `-DownloadReleaseAssets`。
5. 打开 Creator Studio，在 `SadTalker 引擎` 面板中填写：
   - `repo_dir`
   - `python_exe`
   - `checkpoint_dir`
   - `source_image`

## 示例

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation\tools\digital_human
powershell -ExecutionPolicy Bypass -File .\install_sadtalker_workspace.ps1 `
  -PythonExe "C:\Python310\python.exe" `
  -CreateVenv `
  -InstallRequirements
```

如果你的环境已经能跑 SadTalker，只需要把对应路径填回前端页面即可，系统生成视频时会自动调用它。
