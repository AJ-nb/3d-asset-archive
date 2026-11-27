# 桌面音量控制器 · 双镜头样片

[观看 MP4](volume-control.mp4) · [可编辑 Blender 工程](motion.blend) · [逐镜清单](shots.json) · [制片脚本](make_film.py)

3 秒，640 × 360，24 fps，无声。前 32 帧从较低机位缓慢升起，交代整机、旋钮和按键的位置。第 33 帧切到面盘近景，相机缓慢推进，红色指针随滚花旋钮转过 166° 并停稳。两个机位已绑定至工程时间线标记，可在相机视图播放。

## 重新出片

以下命令在本目录运行。需要 Python 3、Blender 和带 libx264 的 FFmpeg。`renders` 和新的 MP4 路径应尚未存在。可给渲染命令追加 `--blender "/path/to/blender"`。

```sh
python ../../scripts/render_batch.py render shots.json --out renders
ffmpeg -n -framerate 24 -start_number 1 -i "renders/shots/reveal/frame_%06d.png" -framerate 24 -start_number 33 -i "renders/shots/dial/frame_%06d.png" -filter_complex "[0:v][1:v]concat=n=2:v=1:a=0,scale=out_color_matrix=bt709,format=yuv420p[v]" -map "[v]" -c:v libx264 -crf 17 -preset medium -color_range tv -colorspace bt709 -color_primaries bt709 -color_trc iec61966-2-1 -movflags +faststart replay.mp4
```

要重建动画工程，可从随包的[控制器模型](../finished/volume-controller.blend)生成新的独立副本。将 `shots.json` 复制到 `rebuilt/`，即可用同一条渲染命令指向 `rebuilt/shots.json`。

```sh
blender -b --factory-startup --disable-autoexec --python-exit-code 1 -P make_film.py -- ../finished/volume-controller.blend rebuilt/motion.blend
```

## 核验

在 Blender 5.2.2 LTS 重新打开交付工程，外部文件引用列表为空。时间线第 1、32 帧使用整机相机，第 33、52、72 帧使用旋钮相机。指针对象隶属于旋钮，对应第 33、52、72 帧的旋钮 Z 角度分别为 95°、12°、−71°。

交付 MP4 已完整解码为 72 帧 H.264，实际为 640 × 360、24/1 fps、3.000 秒。对成片的逐帧亮度缩略图做差，最大跳变位于第 32 至 33 帧。将切点两侧与 Blender 输出比对，并查看成片的第 1、32、33、52、72 帧，整机完整入画，特写中的红色指针由左经过顶部转向右侧。

使用以下命令读取实际解码帧数，并完整解码检查错误。

```sh
ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=codec_name,width,height,avg_frame_rate,nb_read_frames,duration -of json volume-control.mp4
ffmpeg -v error -xerror -i volume-control.mp4 -f null -
```
