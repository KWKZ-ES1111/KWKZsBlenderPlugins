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
