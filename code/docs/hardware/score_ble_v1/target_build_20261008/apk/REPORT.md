# APK 阶段1交付：真实目标构建条件核查

实际结果：BLOCKED_MISSING_ENVIRONMENT，入口exit2，未调用Android目标编译器。
没有debug APK。此项是L0条件与配置准备，不是Kotlin、资源编译或APK构建PASS。

业务基线：a0ba3d6包含已签6c8e0b8；MainActivity.kt／Protocol.java冻结身份保持。
真实工程已核锁JDK17、Gradle8.9、AGP8.7.3、Kotlin2.0.21、compile/target35、BuildTools34.0.0／min26。
无自定义res新增，现有Manifest和框架theme必须进入资源／Manifest处理，不把宿主Java测试当APK。

缺项：展开的JDK17／Gradle8.9／SDK35／BuildTools34.0.0、用户接受的SDK许可，
以及AGP8.7.3／Kotlin2.0.21和全部传递依赖的离线缓存。PATH只有Java8，不能替代JDK17。
对应ZIP已经下载且新核SHA一致，不必重下。插件缓存粗估0.5～1.5GiB，实际需解析后计量。
Kotlin2.0.21对AGP8.7.3存在官方完全支持表之外的风险，记录但不自行升级。

新入口与6项基础设施测试、两阶段采集和共享九门禁结果分别封存；runner自检PASS不外推APK。
准备方案见../PREPARATION.md，手机权限/扫描/连接/断线/UTF8日志实测步骤见../DEVICE_TEST_PLAN.md，当前仅写步骤。
入口参数见software目录target_build_20261008/README.md。目标编译报错先交原日志与最小方案，不改冻结Activity。

尚未提交／推送本轮新文件；M2复核与共享登记由M2收口，待用户转发，尚未送达。
未来成功构建须另交命令、真实SDK/插件/工具身份、Kotlin/资源任务原日志、debug APK与SHA。
实际Handler/权限回调、安装、无线、真实FPGA ACK和设备仍未测，完整T059不关闭。
