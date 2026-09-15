# 服务器发布约定

这是当前个人网站的部署约定，发生变化时应先检查服务器实际状态再更新本文件。

## 连接

- 本机 SSH 别名：`aliyun-ecs`
- 远程用户：`admin`
- 远程系统：Alibaba Cloud Linux 3
- 不在 Skill、网页或 Markdown 中写入私钥内容。

## 目录

- 远程源文件：`/home/admin/dota-site-source/`
- 公开网页目录：`/var/www/ashfury-dota-root/dota/`
- Nginx 配置：`/etc/nginx/conf.d/dota2-mcp.conf`
- 公开入口：`https://ashfury.cn/dota/`
- 单篇文章：`https://ashfury.cn/dota/reviews/<match_id>/`

## 安全发布顺序

1. 先检查当前 Nginx 配置和目标目录，不覆盖无关网站文件。
2. 发布前备份 Nginx 配置到 `/home/admin/` 下带日期的备份文件。
3. 先上传源文件，再部署公开网页文件。
4. 执行 `sudo nginx -t`；失败时不加载配置、不报告成功。
5. 只使用平滑 reload，不停止 Nginx 服务。
6. 发布后用 HTTPS 检查首页、文章页和 `/dota2/api/match/<match_id>`。

## 失败处理

如果上传失败、Nginx 测试失败或线上页面不是 200：停止后续操作，保留已生成的本地草稿，向用户说明失败环节。不要删除旧站点，不要执行宽范围清理命令。
