# R8-06 首次数字执行申请装配准备

PREPARED_NOT_RUN，九例归总控 S 组。本窗口不生成执行许可，也不运行候选/编译器。入口：同名 software 目录 `m3r08_06.py --request REQUEST.json --output NEW_OUTPUT_DIR`；请求schema=M3_R08_ADMISSION_APPLICATION_REQUEST_V1。

复用01/02/03/05及04收据，追加唯一R7-A TB/observer/R6-2 driver本体、四份冻结输入、9 ROM、2头和编译搜索条件；两个裸ROM别名由C6对应rom文件逐字节复制。C6基础71单元加三份source共74，保留旧C5。输出SOURCE_APPLICATION.zip、APPLICATION.json与申请规范SHA，附完整依赖请求/实际结果及缺项；application永远approved=false/authenticated=false/execution_allowed=false。

实际C6 A申请使用simulation-only clock源；参数/运行时readmem仍未elaboration，六个捕获窗口参数、精确argv/timeout、可信工具执行与收尾、M1真实语义和M2准入未闭。actual_request读取实际ModelSim文件身份并保留六工具原请求；有文件不代表可执行。实际申请预期PENDING_UNKNOWN。

完整合成申请仅测试软件装配结构；自填approved、旧P7开关、漏TB/头、外来端口源或错输出收据拒收。运行用例先在独占输出内保存全部构造输入；03/04前置步骤也各存FULL_INPUT/FULL_ACTUAL，不以摘要代替。当前未执行软件、HDL、EDA或硬件。
