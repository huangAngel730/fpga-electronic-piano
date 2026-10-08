# T058新精确集成构建暂存（M2）

这里只跟踪本说明和.gitignore。candidate/runs/guard_proof含ROM副本和厂商生成
产物全部忽略，不提交FS/VG/波形/工具binary。原T056/60K/原L目录保留。

实际run_20261008_exact_waveform综合完成后因新payload_hold约束对象TA2003失败，
没有PnR/STA/新FS，禁止program/release；源scope/211原证据与报告在新RTL候选目录。
不要把此run的中间report或旧L的.fs当新显示整机交付。

原件/复现范围：code/rtl/138K_try/t058_waveform_integration_20261008/README.md。
下一轮须新源manifest/新SDC对象实核/层级RAM20+2+3后新唯一run目录，不覆盖本次失败。
