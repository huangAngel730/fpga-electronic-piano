# 夜间任务4：D3边界病例静态交付

**静态设计已齐套，L0；D3返修仍PARTIAL，NO_ACTIONABLE_EXECUTION_PENDING_M2。** CASES.json给16个定向病例、完整共享前缀、明确833/834帧日历/RESET/END计划、具体尾部输入及每例预期首拒收；BOUNDARIES.md给原源码行号及边界说明。它是非原CLI兼容的V2提案，16例实际结果均NOT_RUN，不能写16 PASS。

源SHA：ingest.py=`3217f97e57daec534306a213c64566fa111e3116f15a15967ca881847c218e07`；M2 D3_COUNTEREXAMPLE.json=`4a32745969b0a4fe6b5aa7a4e880e96659ad677c9b22d790ff6ee4ce4eda0ee4`。关键行：68–77无独立帧日历；98–105 RESET年龄/清epoch；109–124 FRAME登记due；130–132 END终态；151–156普通RETURN；164–169 CANCEL及最终门禁。

覆盖原漏FRAME2510＋CANCEL2512/END2513、2509合法取消、截止同cycle CANCEL先后、END跨漏帧、RESET在833/834两类deadline−1/=/+1、普通PA/RETURN越过漏帧、取消后仍漏帧、两种合法同cycle偏序。区别保留：年龄833在D834可早复位；FRAME后旧消费/新请求不强加全序；已完成截止后再RESET不是反例。

主窗口与自有只读子智能体仅静态阅读。没有运行CLI/import/病例/测试/编译/EDA/硬件，没有修改旧源/包、正式top/M1模型/共享状态/index；功能消费0，不继承旧额度，不启动N32。未提交、未推送；按总控安排留本地RESULT/RECEIPT领取，不发送工具。

未验：实际软件后继及V2适配未绑定、精确诊断名/同cycle与reset相位需M2冻结、manifest/源ROM/输入身份还需M2批准、所有病例执行与实际首拒收均未验证。下一责任M2绑定路径/合同/软件预算，总控统一整合静态修法，再由获准实现窗口执行最小增量。真人M2待用户转发，尚未送达，board_release_allowed=false。
