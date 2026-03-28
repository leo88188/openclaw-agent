搭建ai知识库项目名knowledge
项目功能是实现 主要负责各团队不同人员拥有的openclaw龙虾的永久记忆管理。对现有数据库元数据，表结构，业务指标，术语，各团队业务知识 的向量化存储和向量化搜索。同时对共享的skill，提示词进行管理和分享。
前端风格要求：1. 原有布局绝对不能乱，保持 grid 8列布局，不能使用SVG连线，不能破坏原有页面结构 2. 流程节点之间用**简洁、美观、干净、现代化的横向连接线**连接，不要复杂图形 3. 已完成节点：绿色线条、绿色边框 4. 进行中节点：蓝色线条、蓝色边框 5. 未开始节点：灰色虚线 6. 线条要圆润、干净、专业，不要生硬 7. 保持原有动画：跳动、呼吸、摇摆 8. 整体风格：企业级后台、简洁清爽、高端 9. 不要改变原有HTML结构，只美化CSS和连接线样式 10. 最终代码必须完整可运行，页面不能错乱 。
div+cdn.tailwindcss.com+jquery+html
<script src="https://cdn.tailwindcss.com"></script> <link href="https://cdn.jsdelivr.net/npm/font-awesome@4.7.0/css/font-awesome.min.css" rel="stylesheet"> <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>

后端（Python）： 
1. 使用 Python FastAPI 框架 2. 支持跨域 3. 连接 MySQL 数据库 4. 集成 Redis 做缓存和实时状态管理 5. 完整RESTful API。


自动连接创建可以在gitee上创建公开项目knowledge,并新建数据库knowledge，功能开发前Figma进行设计是非常有必要的。

其他：在该项目下前后端分离，在不同的目录，由后端脚本加载静态html,api接口通过jquery实现ajax实现，交互组件api.js 组件js等拆分。


---

## 迭代需求 (2026-03-27 12:58)

基于对原始需求的理解，重构优化一下需求文档


---

## 迭代需求 (2026-03-27 18:11)

帮我完善交互


---

## 迭代需求 (2026-03-27 18:56)

按照顺序全部大重构一下


---

## 迭代需求 (2026-03-28 10:57)

刚才中途交互设计的工作 执行失败了，要继续完成任务
