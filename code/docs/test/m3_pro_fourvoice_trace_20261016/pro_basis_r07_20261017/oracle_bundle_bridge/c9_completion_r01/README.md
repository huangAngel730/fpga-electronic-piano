# task-day4 mechanical MATH_INPUT_BUNDLE and old pending cases

状态 L0 / SOURCE_READY / NOT_RUN。math_bundle.build_bundle(request,output_dir)按M1 NEXT_INPUT_CONTRACT保留所有74字段、原source/raw ports/原因/事件/阶段；ROW/FX/ADVANCE/INPUT_AND_APPLY四种逐行索引均不以commit/TX筛去未提交或取消的推进。实际FX输入/结果PCM都只是actual，expected_pcm/expected_fx_input为null。缺模型/输入/plan/audio_stable继续PENDING。

request.schema=M3_D4_C9_MATH_BUNDLE_REQUEST_V1，inputs为role→path/bytes/sha256。public_rows必需，其余缺件列missing_roles；raw_capture/reset_edges若提供，必须与每行source SHA核同，不能提供各自自洽却无关的原件。不会因材料SHA核同自动签真实执行权威，也不生成FRAME_PLAN。

pending_only.run_case仅接受原剩六例，通过冻结helper的六个原函数构造原输入，串行同进程调用旧production.main并记录真实stdout/stderr/exit；不调用旧subprocess runner、不重跑已过正例。只适用99行旧fixture，不签C9或大文件。同进程全局sys.argv/stdio须串行，route明确CALLABLE_ROUTE，旧消费账不改。原两正四负期望原样保留，运行仍归总控新台账。

原C9 C17由总控直接运行旧冻结入口，本包不改原源/期望。两新机械bundle接缝例包含descriptor/raw/reset篡改子例，均NOT_RUN。
