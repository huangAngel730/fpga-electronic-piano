# R02网络只读诊断

Git配置检查exit0：未配置http.proxy/https.proxy，当前http.sslBackend=openssl，http.version未固定；本次进程未发现HTTP_PROXY/HTTPS_PROXY/ALL_PROXY。仅输出是否配置及脱敏host/port，不读取或输出凭据。

默认受限环境Resolve-DnsName github.com -Type A返回“拒绝访问”/exit1；这是该环境API权限结果，不据此认定真实DNS解析错误。

正常提升的curl IPv4 HTTPS诊断：curl.exe -4 -sS -o NUL -w 'http=%{http_code}\n' --connect-timeout 10 --max-time 20 https://github.com。工具返回exit1，原输出“curl: (28) Operation timed out after 20004 milliseconds with 0 bytes received”，同时打印“http=200”。该200不足以证明请求完整成功，20秒超时与零接收字节作为实际失败保留，不签网络恢复。

本文件是上述工具会话输出的摘要/文字转录，不冒称另有同期保存的子进程原始双流文件。未修改Git永久配置/网络设置/远端，未使用凭据；本诊断不计A/C/D功能额度。最终发布仍须实际fetch成功、核并发树及新精确树门禁。
