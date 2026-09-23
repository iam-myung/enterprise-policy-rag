"""应用装配入口（占位）。

`composition` 是唯一装配入口（SPEC §2.1）：负责把 interfaces + application + adapters 组装为可运行依赖图，
禁止全局可变单例与隐式客户端初始化。

Step 10-GREEN 实现。Step 0 禁止写入任何业务实现。
"""
