# M2 Pitch/Mod流水候选（隔离测试，不在正式GPRJ）

数学遵循已签收M1 pitch_mod_fcw。输入采样在E，fcw_valid在E+6 NBA后，E+7可消费；原同拍/异拍NoteOn语义保持。相位只推进一次/采样，流水输入参数/base在E快照，连续请求、bubbles、reset可处理。NoteOn不取消旧结果，围绕声部代次的取消由银行负责。

fractionalROM采用10bit x XORrot1(x) XORrot3(x)双射常量地址重排；1024点域验证，表值及公式不变，解决实际原四槽probe的直通地址Hold违例。不要用旧未编码初版代替新源，也不加keep/delaybuf/放宽约束。

snapshot封装在valid&&ready时只启动一次，四槽各自LFO，只启动occupied槽。保存请求id/source/channel/generation和结果对齐，E+7封装输出并背压保持。cancel立即丢held结果、等待busy流水排空才复用，不回滚已发生LFO推进；reset清全部。request_base_fcw必须与控制snapshot身份同一份银行冻结数据，尚未在正式银行接入，不能把任意变化live槽base拼到旧snapshot。

这里的两份实现只给复现脚本/独立Gowinprobe用。正式M1模块、M2银行、公共接口、R17、音色与码流没有修改。不要作为新上板码流烧录；独立控制链L5不代替最终音画L5或真实Pitch/Mod效果L6。
