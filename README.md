# Blender Plugins

这个仓库包含一些单文件 Blender 插件。

## Bone Axis Reference

用于快速确认骨骼或物体局部朝向。

安装 `bone_axis_reference.py` 并启用 `Bone Axis Reference` 插件。

1. 在 3D 视图中选中一个目标物体。
2. 打开侧边栏 `N` 面板，进入 `Item > Bone Axis Reference`。
3. 在 `Distances` 中输入距离列表，例如 `0.5, 1, 2`。
4. 点击 `Create Axis Reference`。

插件会在目标物体原点创建一个顶点，并沿目标物体局部 `+/-X`、`+/-Y`、`+/-Z` 方向按距离列表创建顶点。同一轴上的顶点会通过边连接，参考物体默认显示在前方，并在再次生成时更新同一目标的已有参考物体。

## Selected Mesh Cleanup Smooth

用于对一个或多个选中的网格物体批量执行清理流程：按距离合并顶点、清除自定义法向数据、添加自动平滑着色。

安装 `selected_mesh_cleanup_smooth.py` 并启用 `Selected Mesh Cleanup Smooth` 插件。

1. 在 3D 视图中选中一个或多个网格物体。
2. 打开侧边栏 `N` 面板，进入 `Item > Mesh Cleanup Smooth`。
3. 按需要调整 `Merge Distance` 和 `Auto Smooth Angle`。
4. 点击 `Cleanup And Auto Smooth`。

`Merge Distance` 用于合并重合或近距离顶点；`Auto Smooth Angle` 用于设置自动平滑角度。

## Origin To Selected Edge

用于把活动网格物体的原点移动到一条已选边的中点，并让物体本地 `Z` 轴对齐这条边。网格在世界空间中的外观位置会保持不变。

安装 `origin_to_selected_edge.py` 并启用 `Origin To Selected Edge` 插件。

1. 选中一个网格物体并进入编辑模式。
2. 只选中一条边。
3. 回到物体模式。
4. 在 3D 视图中右键，进入 `Set Origin > Selected Edge`。

如果该物体的 Mesh 数据被多个物体共享，插件会先为活动物体复制一份 Mesh，避免影响其他共享同一数据的物体。

不同 Blender 版本的 `Set Origin` 菜单类名不完全一致；插件会尝试挂到常见的 `Set Origin` 子菜单，并额外在物体模式右键菜单顶层提供 `Set Origin to Selected Edge` 兜底入口。

## Align Y Axis To 3D Cursor

用于保持活动网格物体当前本地 `Z` 轴方向不变，只通过沿 `Z` 轴移动原点、并绕 `Z` 轴旋转扭转角，让本地 `Y` 轴指向 3D 游标。网格在世界空间中的外观位置会保持不变。

安装 `align_y_axis_to_cursor.py` 并启用 `Align Y Axis To 3D Cursor` 插件。

1. 选中一个网格物体。
2. 把 3D 游标放到希望本地 `Y` 轴指向的位置。
3. 在物体模式的 3D 视图中右键，点击 `Align Y Axis To 3D Cursor`。

如果 3D 游标正好位于当前本地 `Z` 轴线上，工具会把原点沿 `Z` 轴移动到游标处，并保持当前 `Y` 轴扭转，因为这时所有绕 `Z` 的 `Y` 方向都同样接近。

## Weight Gradient Bridge

用于给「两端固定在金属框架上、中间要平滑变形」的柔性件（橡胶套、软管、波纹管）快速生成互补的蒙皮权重渐变：一端锚区的顶点得到最大权重，另一端锚区得到最小权重，中间的顶点按到两组锚区的距离比例自动插值过渡。

安装 `weight_gradient_bridge.py` 并启用 `Weight Gradient Bridge` 插件。

准备：先在网格上建两个顶点组（例如按两端骨命名），各自只选中对应端的一圈顶点并 `Assign` 权重 1.0，作为两端锚区。

1. 选中网格物体（物体模式）。
2. 打开侧边栏 `N` 面板，进入 `Item > Weight Gradient Bridge`。
3. `Group A` / `Group B` 分别选择两个锚区顶点组。
4. `Max Weight (A End)` 与 `Min Weight (B End)` 设成两端想要的权重（默认 1 / 0，即 A 组从 A 端 1 渐变到 B 端 0）。
5. 点击 `Apply Gradient`。

A 组会被整段填充渐变；勾选 `Write Complement To Group B`（默认开）时，B 组同步写入互补值（两端互换的镜像渐变），使两个组在任意顶点附近互补，适合绑定两根骨的软管类形变。

注意边界：目前每个顶点按到两组锚区的直线距离算过渡比例，弯得比较厉害的软管中间段可能不够贴曲面；以及会整体覆盖 A/B 两组原有权重。

## Curve Direction Arrows

用于在曲线物体上生成箭头，直观标出曲线的走向。

安装 `curve_direction_arrows.py` 并启用 `Curve Direction Arrows` 插件。

1. 在物体模式选中一个或多个曲线物体。
2. 打开侧边栏 `N` 面板，进入 `Item > Curve Direction Arrows`。
3. 选择 `Style`（Solid 立体箭头 / Flat 扁平箭头）与 `Distribution`（Count 固定数量 / Spacing 按弧长间距）。
4. 调整 `Size`、`Offset`、`Up Axis` 等参数后点击 `Create Direction Arrows`。

箭头沿曲线切线方向生成。`Count` 模式在每个曲线物体上均匀分布指定数量；`Spacing` 模式按弧长间隔放置。`Size Mode` 设为 `Relative` 时箭头长度按曲线总长度的百分比计算，`Absolute` 时使用 Blender 单位。`Offset` 沿选定上方向抬起箭头，避免箭头与曲线重叠。开启 `Follow Curve` 后箭头会父级到曲线，曲线移动时箭头跟随。

生成的箭头是普通网格物体，共用 `Curve Direction Arrow` 材质。点击 `Clear Direction Arrows` 删除选中曲线对应的箭头；没有选中曲线时会清空场景里所有生成的箭头。

注意边界：箭头不会实时跟随曲线形状的修改，改完曲线后需要再点一次 `Create Direction Arrows` 重新生成；采样基于曲线原始数据，曲线物体上的修改器（如 Array）不会计入；关闭 `Update Existing` 时每次都会新建一套箭头物体，旧箭头需要手动清理。
