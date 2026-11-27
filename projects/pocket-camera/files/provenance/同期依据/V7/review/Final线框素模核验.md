# Final 镜头与云台线框、素模复核

两份工程分别由 Blender 重新打开。Final 的 SHA-256 为 `136a14ee3a5d632842276f49a599b920a55c24ea7e46b47e3f4f37b9a6471392`，基线为 `bfe87db4162421066892bbb4beccead4ad88349b44713d4951a2d47e43aeefc3`。使用第 62 帧相同正交相机、可见零件、工作台素模照明和可见边求值设置。六张 Final 原图均为 1440 × 1440 像素。

[Final 六图联系表](镜头与云台线框素模-Final.jpg) · [几何与动作等价报告](source-equivalence.json) · [像素差异记录](source-equivalence-views.json)

| 机位 | Final 原图 | 与基线存在差异的像素数 | 最大 8 位通道差 |
|---|---|---:|---:|
| 双摄正面 | [素模](mesh-final/01-face-clay.png) | 0 | 0 |
| 双摄正面 | [求值线框](mesh-final/01-face-wire.png) | 0 | 0 |
| 云台后侧与机身 | [素模](mesh-final/02-joint-clay.png) | 0 | 0 |
| 云台后侧与机身 | [求值线框](mesh-final/02-joint-wire.png) | 0 | 0 |
| 支承件与转轴 | [素模](mesh-final/03-internal-clay.png) | 0 | 0 |
| 支承件与转轴 | [求值线框](mesh-final/03-internal-wire.png) | 0 | 0 |

逐像素一致的图像为 6/6。三机位求值网格投影可见边坐标逐条一致。

素模使用单一覆盖表面，几何、轮廓和可见边可用于检查倒角与装配。支臂材质着色的效果请查看同版正式渲染。
