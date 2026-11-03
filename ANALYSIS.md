# Tizen tizen_base 的 MLGO 改动与 LLVM 22.1.8 移植分析

分析日期：2026-11-03（Asia/Shanghai）。工作目录：`/home/linhao/Toolchain/development/mlgo_llvm_port`。

## 结论

**本次克隆的 tizen_base 已基于上游 llvmorg-22.1.8，无需跨 LLVM 版本移植。**
核心是 Tizen 的预编译 TensorFlow/XLA AOT 资产打包，以及 runtime 对象内嵌/导出控制。
相对于上游没有新增 MLInlineAdvisor、ReleaseModeModelRunner 或寄存器分配 advisor 的 C++ 实现。

- 上游之上共 **14 个提交，全部为非 merge commit**。明确 MLGO 相关 **2 个**；另保守列出 **3 个待确认的通用构建关联提交**，共导出并试打 **5 个候选补丁**。
- 5 个原始完整补丁依次试打结果：**干净 4、有冲突 1、已存在/空变更跳过 0**。唯一冲突已执行 `git am --skip`，所以“因冲突跳过”另计 **1**。两个明确 MLGO 补丁均干净。
- 唯一冲突来自待确认的通用 ThinLTO 回退补丁；缺少非 MLGO 的 `0012` 导致上下文分歧，不能把它算成 LLVM 22.1.8 的 MLGO 接口不兼容。
- 同时有 **inliner size 模型和 regalloc eviction 模型**，分别为 `InlinerSizeModel.h/.o`、`RegAllocEvictModel.h/.o`；三个压缩包覆盖 ARM、AArch64、x86-64。没有发现打包的 regalloc priority 模型，也没有可重新训练的 SavedModel 或 `.tflite` 文件。
- 本次只做 Git 导出、顺序试打和静态分析，**没有进行 CMake 配置、编译、运行模型或性能验证**。补丁可应用不等于模型质量和构建可用性已验证。

## 来源、版本、大小和基线

源：`git://review.tizen.org/git/platform/upstream/llvm`，分支 `tizen_base`。
上游：`https://github.com/llvm/llvm-project.git`。均使用指定源，没有切换镜像。

`git -C llvm-tizen log -1 --format='%H %ad %s'` 原始输出：

```text
f999bd406c0a70fe8107aa992164fe6945c5d46a Fri Oct 16 11:03:12 2026 +0900 Revert clang bootstrap + ThinLTO, fall back to GCC
```

版本是 **LLVM_VERSION_MAJOR=22、MINOR=1、PATCH=8**。
`llvm/CMakeLists.txt:19` 引入 `../cmake/Modules/LLVMVersion.cmake`，具体值定义在后者第 4、7、10 行；当前 CMakeLists 并未直接写死这三个数值。

| 大小口径 | 结果 |
|---|---:|
| 克隆后目录磁盘占用（`du -sh llvm-tizen`） | 7.0 GiB（工具显示 `7.0G`） |
| 克隆后目录表观大小（`du -sb`，含 .git） | 6,983,272,660 bytes |
| 刚克隆后的 .git 表观大小 | 4,871,917,115 bytes |
| tizen_base 跟踪 blob 数 | 169,038 |
| tizen_base 跟踪 blob 内容合计 | 2,111,355,621 bytes（约 1.966 GiB） |

Git 对象库共享完整克隆的历史和 refs，其占用不能当成 tizen_base 独占的分支增量大小；分支源码大小用 blob 合计表达。
后续上游 fetch、worktree 和试打会增加本地占用，上表保留克隆时口径。

执行了完整标签获取：

```sh
git -C llvm-tizen remote add upstream https://github.com/llvm/llvm-project.git
git -C llvm-tizen fetch upstream --tags 'refs/tags/llvmorg-*:refs/tags/llvmorg-*'
```

无需额外拉取 release 分支，标签包含的历史足以确定基线。

| 检查 | 结果 |
|---|---|
| `git describe --tags --abbrev=0` | `accepted/tizen/base/20261022.050448`（Tizen 自有标签，不能当成上游基线） |
| `git describe --tags --abbrev=0 --match 'llvmorg-*' tizen_base` | **llvmorg-22.1.8** |
| 上游 tag 对象（`git ls-remote`） | `e013073558445169e8732e25fa86e9913bfdd24e` |
| 上游 tag peeled commit | `ca7933e47d3a3451d81e72ac174dcb5aa28b59d1` |
| `git merge-base tizen_base llvmorg-22.1.8` | `ca7933e47d3a3451d81e72ac174dcb5aa28b59d1` |
| BASE_TAG 全部可达提交数 | 565,548 |
| tizen_base 全部可达提交数 | 565,562 |
| `BASE_TAG..tizen_base` 提交数 / 非合并数 / 合并数 | 14 / 14 / 0 |
| 明确 MLGO / 待确认 / 候选补丁总数 | 2 / 3 / 5 |

BASE_TAG commit 与 merge-base 相同，证明该 release 是直接祖先。
`packaging/SOURCE_PROVENANCE` 也记录同一个 22.1.8 commit；它作为交叉核对，基线结论依据实际 Git 图和上游 refs。
标题为 “Merge MLGO ...” 的 `fd7a4929c0e4` 实际是单父提交（squash），因此被 `--no-merges` 和 `format-patch` 正常包含。

## 筛选口径与产物

对全部 14 个非合并提交逐个检查完整提交信息、改动路径、增删行及 spec 的相关上下文，匹配：
`mlgo / MLGO / tflite / TFLite / tensorflow / AOT / aot / ml-inliner / MLInlineAdvisor / ReleaseModeModelRunner / regalloc advisor / RegAllocEvictionAdvisor / models/ / InlineAdvisor`。
大小写不敏感；不能仅凭提交标题判断贡献。

`commits_all.txt` 保留要求的 `git log --oneline --no-merges BASE_TAG..tizen_base` 顺序。
`commits_mlgo.txt` 按 `format-patch` 的历史顺序列出完整 SHA、原编号、理由与“明确/待确认”。
三个待确认项仅命中 spec 的 MLGO 邻近上下文，实际增删的是通用工具链配置；保守收录供审计，**不应认定为新增 MLGO 功能或核心必需依赖**。

未纳入的提交为 `0002` Tizen vendor、`0003` ASan/libatomic、`0004` 打包版本升级、`0005` ARM 编译器选项、`0006` gold plugin、`0008–0009` libc++ EH、`0010` libc++ runtimes 编译器选择、`0012` 通用 `-fno-inline-functions` 清理。
其中 `0004` 对复用整份旧 packaging 补丁的版本正确性有用，`0012` 对通用回退序列的上下文完整性有用；这不把它们变成 MLGO 功能改动。它们的完整补丁保留在本地 `patches_all/`。

| 产物 | 内容 |
|---|---|
| `patches_all/`（仅本地） | `git format-patch BASE_TAG..tizen_base` 的全部 14 个原始补丁 |
| `patches_mlgo/*.patch`（本地） | 从上述目录逐字节复制的 5 个原始完整补丁，编号保留 0001/0007/0011/0013/0014 |
| `patches_mlgo/code_only/0001-Add-packaging.patch` | 用同一提交重新 format-patch，仅通过 pathspec 排除三个模型包；用于 GitHub |
| `packaging_tizen_base/`（本地） | 源分支 HEAD 的 packaging 原样副本，包含三个模型压缩包 |
| `packaging_tizen_base/`（GitHub） | 同一副本中的全部文本文件；三个模型包通过 .gitignore 排除 |
| `models_list.txt` | find 清单、模型包 SHA256、关键包内文件路径与字节数 |
| `apply_22.1.8.md` | 原始完整补丁试打的逐项日志、冲突片段和 skip 结果 |

原始 `0001` 包含三个模型压缩包的 Git binary patch，并超过 20 MB，故不会推送；**不能把模型编码进文本补丁来绕过不上传模型的约束**。
代码版 `0001` 不包含模型内容，也不含二进制 diff 占位；它仍引用外部模型源文件，单独下载 GitHub 产物不足以重现 RPM 构建。
其他四个发布补丁与原始补丁一致。`code_only/0001` 与本地原始 `0001` 是替代关系，不应重复应用。

## 每个候选 MLGO patch

### 0001 — Add packaging（明确）

提交：`3d723549f6037bdab5be47aaa6e6354fd3707d89`；试打：**干净**。发布补丁：[查看](patches_mlgo/code_only/0001-Add-packaging.patch)。

改动文件：

- `packaging/llvm.manifest`
- `packaging/llvm.spec`
- `packaging/mlgo_aarch_model.tar.gz`
- `packaging/mlgo_arm_model.tar.gz`
- `packaging/mlgo_x86_model.tar.gz`

此提交新增整份 Tizen packaging，而非只添加 MLGO 行；其中含 manifest、spec 及三份模型包。
spec 为 armv7l/aarch64/x86_64 默认开启 `%bcond_without mlgo`，解包到 `mlgo_verify_assets`，以 `.h/.o` override 接入 inliner 和 regalloc eviction；并配置 XLA runtime 对象内嵌和不导出独立 runtime 库。

**构建依赖：** 三个架构对应的预编译模型、`mlgo_sysroot/include`、`xla_aot_runtime_src`、五个 XLA runtime `.o`，以及常规 CMake/Ninja/Python 开发工具。这个打包路径不需要在 GBS 内安装 TensorFlow Python 或运行 `saved_model_cli`；也未启用 TFLite。
**运行依赖：** 编译器内执行模型推理，需要已链接的模型及 XLA native runtime；不需要推理时加载 SavedModel、TensorFlow Python 或 TFLite。最终 ELF 的完整动态依赖未做构建验证。

**配置：** spec 使用 `TENSORFLOW_AOT_PATH`、四个 `LLVM_OVERRIDE_MODEL_HEADER/OBJECT_*`、`LLVM_INLINER_MODEL_PATH=none`、`LLVM_RAEVICT_MODEL_PATH=none`，以及 `LLVM_MLGO_EXPORT_TF_XLA_RUNTIME=OFF`、`LLVM_MLGO_EMBED_TF_XLA_RUNTIME_OBJECTS=...`。
前一组是上游已有接口；后两个接口由后续 `0007` 实现，不能误认为 `0001` 自身已经定义它们。
RPM 宏 `mlgo_build_jobs` 默认 6，`mlgo_verify_configure_only` 默认 0；后者开启时检查 override、对象架构、不回退 mock、不安装 runtime archive，成功标记后故意 `exit 86`。

**新增运行期选项：无。** spec 不给最终 clang 配置自动添加 MLGO release 开关。

**移植注意：** 原始补丁的 spec 仍写 `llvm_version 21`、`Version: 21.1.1`；HEAD 中已经由非 MLGO 的 `0004` 更新为 22.1.8。本次按选定补丁试打会保留旧版本声明，因此不能直接把这个试打 worktree 当成可发布的 22.1.8 RPM recipe。完整 HEAD 的 spec 已另存于 `packaging_tizen_base/llvm.spec`。

原始补丁：`0001-Add-packaging.patch`，112,077,030 bytes；SHA256：`f37d7ba4c339e310c41c77c70fbeb611d1280824a30cc7f2cb2029708482d88b`。

### 0007 — Merge MLGO AOT compilation support and optimization improvements（明确）

提交：`fd7a4929c0e424d564cdd1f0c55af9153dcea321`；试打：**干净**。发布补丁：[查看](patches_mlgo/0007-Merge-MLGO-AOT-compilation-support-and-optimization-.patch)。

改动文件：

- `llvm/CMakeLists.txt`
- `llvm/cmake/modules/TensorFlowCompile.cmake`

真正的 MLGO 源码增量：仅改两个 CMake 文件，40 行新增、7 行删除。

1. 新增 `LLVM_MLGO_EXPORT_TF_XLA_RUNTIME`（BOOL，默认 ON）。关闭时不安装/导出 `tf_xla_runtime`，不将其加入 `LLVM_EXPORTS`，并省去模型组件的该项 `MLLinkDeps`。
2. 新增 `LLVM_MLGO_EMBED_TF_XLA_RUNTIME_OBJECTS`（STRING，默认空），接受分号分隔的原生 `.o` 路径，将其加入 `GeneratedMLSources`。
3. 通过全局属性 `LLVM_MLGO_TF_XLA_RUNTIME_OBJECTS_EMBEDDED` 只内嵌一次。优先附到 InlinerSizeModel/LLVMAnalysis；未启用 inliner 时可附到 regalloc 模型组件。LLVMCodeGen 的 LINK_COMPONENTS 包含 Analysis。
4. `MLDeps` 仍保留 `tf_xla_runtime` 构建依赖；OFF 表示不导出/不独立链接该 archive，不代表 runtime 代码完全消失。

**构建依赖：** TensorFlow/XLA 头文件、AOT 模型 `.h/.o`、runtime target 和可选 runtime 对象列表。使用 spec 的预编译 override 路径无需 TensorFlow Python；改用 SavedModel 编译路径则仍需上游已有的 `TENSORFLOW_AOT_COMPILER`/`saved_model_cli aot_compile_cpu`。
**运行依赖：** XLA native 推理代码改为内嵌在 LLVM 组件；不新增 TensorFlow Python/TFLite 动态加载需求。

**新增 CMake 选项恰为上述两个。新增运行期选项：无。**
提交信息提到模型包、spec、regalloc 支持与 `TENSORFLOW_AOT_COMPILER` 配置，但当前历史中的实际 diff 不新增这些文件或既有选项；模型资产已经在 `0001`，AOT/override/advisor 框架已在上游 BASE_TAG。

该补丁对目标标签干净应用。静态上应保持 ON 的上游默认路径；使用 OFF 时需同时提供完整 runtime 对象，否则链接可能缺符号。全局“一次”规则和各组件的静态/共享链接结果仍需后续实际构建确认。

原始补丁：`0007-Merge-MLGO-AOT-compilation-support-and-optimization-.patch`，5,631 bytes；SHA256：`1da2a0522f96b1a70e9fbaca51b00d50326b092da875414651eff02928da327c`。

### 0011 — optimize llvm performance（待确认）

提交：`7e4dc62d8ac01f90488a0cc8e0f34f8373228c84`；试打：**干净**。发布补丁：[查看](patches_mlgo/0011-optimize-llvm-performance.patch)。

改动文件：

- `packaging/llvm.spec`

**待确认，仅间接构建关联。** 改 x86_64 的 Clang bootstrap、`-O3`、ThinLTO、编译选项清理与工具静态链接；MLGO 行只在 diff 上下文中，模型和 advisor 没变。

**构建依赖：** 在相应 RPM 条件下增加 Clang/LLVM/libllvm；使用 lld、llvm-ar、llvm-ranlib 和 ThinLTO。可能影响预编译 XLA native 对象与 LLVM bitcode 混合链接，但没有证据表明这是 MLGO 功能的必要条件。
**运行依赖：** 调整 LLVM/Clang 动态或静态链接方式；不增加 TensorFlow/TFLite 推理依赖。

**新使用的配置（不是新增定义）：** `LLVM_ENABLE_LTO=Thin`、`CMAKE_AR`、`CMAKE_RANLIB`、C/C++ 编译器/链接器 flags，及 `LLVM_LINK_LLVM_DYLIB=OFF`、`CLANG_LINK_CLANG_DYLIB=OFF` 的 x86_64 分支。
**新增 MLGO CMake/运行期选项：均无。** 在 HEAD 被 `0014` 回退，不建议作为核心 MLGO 移植必需项。

原始补丁：`0011-optimize-llvm-performance.patch`，3,597 bytes；SHA256：`5ced5987405f6af95b35cc7a0a99f9e595f1b3d84caacaf4457eed6e539a4974`。

### 0013 — packaging: fix llvm-static-devel with ThinLTO（待确认）

提交：`67619ec8bbbac7238a6cfc33a481ccfbcd12206f`；试打：**干净**。发布补丁：[查看](patches_mlgo/0013-packaging-fix-llvm-static-devel-with-ThinLTO.patch)。

改动文件：

- `packaging/llvm-static-archives-native.py`
- `packaging/llvm.spec`

**待确认，仅间接安装/静态链接关联。** 增加 `llvm-static-archives-native.py`（788 行），在 x86_64 的 `%install` 末尾把静态 archive 中的 LLVM bitcode 成员转换为 native 对象，再重建确定性 GNU archive/index，保持 native 成员、顺序和重复成员名。
新增 `Source1005` 与条件 `BuildRequires: util-linux`，调用构建出的 clang-22、llvm-dis、llvm-nm，限定 4 个 job/4 GiB 地址空间。

**构建/安装依赖：** Python3、相应 LLVM 工具和本地 archive 工具；目的是普通 GNU linker/strip 能处理安装的静态库，不是模型转换或训练。
**运行依赖：** 不增加 MLGO 推理依赖；可能影响含模型/runtime 对象的组件归档的下游消费方式。
**新增 MLGO CMake/运行期选项：均无。** spec 中的 MLGO Source 行仅为上下文；该通用处理已在 HEAD 被 `0014` 删除。

原始补丁：`0013-packaging-fix-llvm-static-devel-with-ThinLTO.patch`，46,389 bytes；SHA256：`6e7baee17c34a7eec77111435f68e06bfc44c8bd9f95076f8f1a49a79d1aad75`。

### 0014 — Revert clang bootstrap + ThinLTO, fall back to GCC（待确认）

提交：`f999bd406c0a70fe8107aa992164fe6945c5d46a`；试打：**有冲突**。发布补丁：[查看](patches_mlgo/0014-Revert-clang-bootstrap-ThinLTO-fall-back-to-GCC.patch)。

改动文件：

- `packaging/llvm-static-archives-native.py`
- `packaging/llvm.spec`

**待确认，仅间接构建关联。** 删除上一项的脚本及安装转换，撤销 x86_64 Clang bootstrap、`-O3`/ThinLTO、静态链接特殊分支和优化 flags 清理，恢复 GCC/default 工具链。模型包、MLGO bcond、AOT overrides 和 runtime 内嵌配置保留。

**构建依赖：** 移除上述 Clang bootstrap 与 util-linux 的条件依赖；回退通用构建配置。
**运行依赖：** 不新加 MLGO 依赖。
**新增 MLGO CMake/运行期选项：均无。**

**冲突原因初判：** 此回退按其真实父提交删除包含 `0012` 添加的两条 `-fno-inline-functions` 过滤规则的完整 block；本次候选子集没有 `0012`。三方合并面对“目标侧 block 少两行、补丁侧删除整个 block”的修改/删除分歧，在 `packaging/llvm.spec` 产生文本冲突。冲突发生在通用 CFLAGS/CXXFLAGS block；两个 MLGO CMake 文件不冲突。已记录并 `git am --skip`，未尝试人工解决或补齐非 MLGO 提交。

原始补丁：`0014-Revert-clang-bootstrap-ThinLTO-fall-back-to-GCC.patch`，47,268 bytes；SHA256：`b265ae087fe2d8e650b54974a8cc2d1e09820cbcec9ee696ff440ae5c3c4d8ea`。

## 配置接口与构建期/运行期依赖

| 选项 | 是否 Tizen 新增 | 本分支用途 |
|---|---|---|
| `LLVM_MLGO_EXPORT_TF_XLA_RUNTIME` | 是，0007 | 默认 ON；spec 设 OFF，避免安装/导出独立 `tf_xla_runtime` |
| `LLVM_MLGO_EMBED_TF_XLA_RUNTIME_OBJECTS` | 是，0007 | 默认空；spec 指向五个预编译 XLA `.o`，只内嵌一次 |
| `TENSORFLOW_AOT_PATH` | 否，上游已有 | 指向 bundled `mlgo_sysroot`，提供 include 与 `xla_aot_runtime_src` |
| `TENSORFLOW_AOT_COMPILER` | 否，上游已有 | SavedModel AOT 编译工具路径；有效 override 路径不调用它 |
| `LLVM_OVERRIDE_MODEL_HEADER_INLINERSIZEMODEL` / `LLVM_OVERRIDE_MODEL_OBJECT_INLINERSIZEMODEL` | 否，上游已有 | 提供 inliner 的 `.h/.o` |
| `LLVM_OVERRIDE_MODEL_HEADER_REGALLOCEVICTMODEL` / `LLVM_OVERRIDE_MODEL_OBJECT_REGALLOCEVICTMODEL` | 否，上游已有 | 提供 regalloc eviction 的 `.h/.o` |
| `LLVM_INLINER_MODEL_PATH` / `LLVM_RAEVICT_MODEL_PATH` | 否，上游已有 | 支持 none/autogenerate/download/路径；spec 禁用分支设 none，启用分支用 override |
| `LLVM_HAVE_TFLITE` | 否，上游已有 | 另一路 development/runtime-loadable 模型支持；spec 未启用 |

`LLVM_HAVE_TF_AOT` 由非空 `TENSORFLOW_AOT_PATH` 配置，模型启用时设置 `LLVM_HAVE_TF_AOT_INLINERSIZEMODEL`/`LLVM_HAVE_TF_AOT_REGALLOCEVICTMODEL` 编译定义。
**有有效 `.h/.o` override 时，模型路径为 none 也仍启用模型**：`tf_find_and_compile` 先检查两个 override 文件是否存在，再检查 none；这是上游原有逻辑。
若只设置 header override 而对应对象不存在，顶层已把路径设为 none，可能静默跳过模型；spec 的 configure-only 断言用于发现此类错误。不能依赖“指定了参数”来证明模型真的编入。

bundled `xla_aot_runtime_src/CMakeLists.txt` 先建立 dummy C 静态 target，POST_BUILD 用 `libtf_xla_runtime_prebuilt.a` 覆盖输出；ARM/x86 版本还检查复制结果。即使禁止导出 runtime，这个 target 仍因 `MLDeps` 构建。
模型头包含 TensorFlow/XLA C++ 头文件，故“无需 TensorFlow Python”不等于“完全无需 TensorFlow/XLA 构建资产”。
包内也有 `_ml_dtypes_ext.so` 等 sysroot 附带文件；仅凭它们被打包，不能认定发布的 clang 推理时要加载 Python 扩展。

### 运行期选项

Tizen 这 14 个提交没有新增 MLGO 命令行选项，未修改以下注册点；这些都是 BASE_TAG 已有的接口：

| 参数（Clang 传递形式） | 模式/含义 | 注册源文件 |
|---|---|---|
| `-mllvm -enable-ml-inliner=release` | default/development/release；release 使用 AOT inliner，描述注明针对 `-Oz` | `llvm/lib/Passes/PassBuilderPipelines.cpp:159` |
| `-mllvm -regalloc-enable-advisor=release` | default/development/release；release 使用 AOT eviction | `llvm/lib/CodeGen/RegAllocEvictionAdvisor.cpp:31` |
| `-mllvm -regalloc-enable-priority-advisor=release` | 上游 priority 接口另有 dummy 模式；本次没有提供其模型，不能当成已可用功能 | `llvm/lib/CodeGen/RegAllocPriorityAdvisor.cpp:24` |

前两个默认值仍是 `default`，即编入 AOT 模型不等于自动选择 ML 策略。
例如在后续真正完成构建和验证后，可测试 `clang -Oz -mllvm -enable-ml-inliner=release -mllvm -regalloc-enable-advisor=release ...`；此处是接口示例，本次未执行。
development 模式及其运行期可加载模型需要另行配置 TFLite；本分支默认 RPM 配方走 release AOT 路径。

## 模型和大文件

三个包都包含 inliner 和 eviction 模型，不是“一包一个策略”。名称中的架构由模型 `.o` 的 ELF header 验证，代表运行模型推理代码的 LLVM/Clang host 架构，不足以证明训练目标架构或质量。

| 源包 | 压缩 bytes / MiB | Inliner `.h` / `.o` bytes | Eviction `.h` / `.o` bytes | ELF |
|---|---:|---:|---:|---|
| `mlgo_aarch_model.tar.gz` | 30,461,764 / 29.051 | 76,664 / 374,272 | 48,645 / 75,984 | AArch64 / ELF64 |
| `mlgo_arm_model.tar.gz` | 28,477,748 / 27.158 | 76,664 / 379,060 | 48,825 / 82,352 | ARM / ELF32 |
| `mlgo_x86_model.tar.gz` | 28,652,731 / 27.325 | 76,859 / 376,928 | 48,825 / 80,792 | X86-64 / ELF64 |

源包位于 `llvm-tizen/packaging/`，本地原样副本位于 `packaging_tizen_base/`。包内模型均在根目录；spec 解包后的路径为 `mlgo_verify_assets/InlinerSizeModel.h/.o` 和 `mlgo_verify_assets/RegAllocEvictModel.h/.o`。
configure COPYONLY 后预期为 `build/lib/Analysis/InlinerSizeModel.h/.o`、`build/lib/CodeGen/RegAllocEvictModel.h/.o`。

每包还有五个 `xla_runtime_objects/*.o`，以及 `mlgo_sysroot/xla_aot_runtime_src/libtf_xla_runtime_prebuilt.a`。
后者 ARM 为 20,282,784 bytes（低于 20 MiB、但超过十进制 20 MB），AArch64 为 39,844,528 bytes，x86 为 22,484,724 bytes；全都仅列清单，不上传。
每包 12,782 个成员；展开普通文件合计 ARM 220,301,213、AArch64 239,884,520、x86 222,634,336 bytes。

三包内未发现 `.pb`/`.pbtxt`/`.tflite` 的模型数据文件或训练 provenance/manifest，主要是已编译模型、运行库、头文件和许可证。
无法仅凭产物确认训练集、训练版本或优于启发式算法，也不能因 spec 禁止 autogenerate 就证明包内模型训练质量。
`llvm/lib/Analysis/models/` 的 gen-inline/gen-regalloc 等 Python 文件是上游测试模型生成器；`llvm/unittests/Analysis/Inputs/ir2native_x86_64_model/saved_model.pbtxt` 是另一项测试数据，不是这两套发布 AOT 模型。
`clang-tools-extra/clangd/quality/model/forest.json` 为 25,784,677 bytes，是 clangd completion 模型，不能算成 Tizen MLGO 补丁新增模型。
find 同时列出超过阈值的 `.git` pack/idx/rev，这些是对象存储，不是推理模型。

完整路径/精确大小和三个压缩包 SHA256 见 [models_list.txt](models_list.txt)。find 的 `+20M` 采用 MiB 单位；发布检查另外采用更严格的 20,000,000 bytes 上限，两种口径下的大文件均未上传。

### 静态接口检查及限度

三个架构的 inliner 生成头都声明 35 个输入，而 22.1.8 的普通标量输入列表有 38 个（不含可选 IR2Vec embedding）。
缺少 `switch_default_dest_penalty`、`is_callee_avail_external`、`is_caller_avail_external`。
eviction 生成头为 20 个输入，对应源码 21 个，缺少 `nr_urgent`。
所发现的模型输入名都属于对应源码特征集合；输出名分别为 `fetch_inlining_decision` 和 `fetch_index_to_evict`，与默认 feed/fetch 前缀契约一致。

`ReleaseModeModelRunner.h:117` 的 `populateTensor` 在模型没有某个特征时让 `MLModelRunner` 建立 scratch buffer，因此“模型输入更少”本身不能判为 ABI 冲突；但模型未消费这些额外特征。
这只是头文件/源码级证据，未验证每个类型/shape 的实际绑定、XLA C++ ABI、完整链接符号、CPU 指令集要求和决策质量。

## 22.1.8 冲突汇总和移植建议

| 补丁 | 分类 | 原始补丁顺序试打 | 解释 |
|---|---|---|---|
| 0001 | 明确 | 干净 | 上游没有 packaging，新增文件可应用；但 recipe 版本还是 21.1.1 |
| 0007 | 明确 | 干净 | 目标就是当前分支的上游基线；两个 CMake 文件上下文一致 |
| 0011 | 待确认 | 干净 | 通用 bootstrap/ThinLTO 改动可套用到已加入的 spec |
| 0013 | 待确认 | 干净 | 新增转换脚本和安装步骤可套用 |
| 0014 | 待确认 | 有冲突，随后 skip | 未纳入 0012，导致待删除的优化参数 block 与父版本不一致 |

没有观察到 MLGO C++ API、模型 runner 或 advisor 文件的合并冲突。
详细原始输出、冲突文件、冲突片段及未合并索引见 [apply_22.1.8.md](apply_22.1.8.md)。
试打采用原始完整 `0001`（含模型），不是 GitHub 的 code_only 版。
试打结束 worktree 干净，没有进行中的 am；因为跳过 `0014`，其中仍保留 `0011/0013` 的通用改动，**它不等于 tizen_base 的最终树**。

建议以 `0007` 的两个新增 CMake 机制作为核心移植内容，结合 HEAD spec 中的模型 override/runtime 参数；`0001` 是打包和资产载体，不能直接当成纯 MLGO 源码修改。
三个待确认的通用构建补丁不是恢复 MLGO 功能所必需，并且在当前分支最终状态已回退。
若目标是复制整个 Tizen RPM 配方，应以 `packaging_tizen_base/llvm.spec` 的 22.1.8 最终状态为依据，并配齐原始模型资产及必要的非 MLGO 打包改动；本次不实施该修改。

后续真正投产前需验证：每个 host 架构的头/对象配对与 XLA ABI、OFF 时无缺符号/重复符号、LLVMAnalysis/LLVMCodeGen 的静态和共享链接、安装后 LLVM CMake exports、release 模式能选到两种 advisor，以及 `-Oz` 大小/性能基准。此清单是移植剩余验证项，本次未执行构建或修复。

## packaging/llvm.spec 原文

以下完整贴出 **tizen_base HEAD** 的 spec（包括所有 MLGO 相关行及条件上下文），与 [packaging_tizen_base/llvm.spec](packaging_tizen_base/llvm.spec) 逐字一致。
重点位置：3–9 MLGO bcond；41–61 Source/宏/全部 BuildRequires；157–168 解包；188–194 AOT/runtime 路径；257–274 CMake 参数；276–341 configure-only 检查（含禁止安装独立 runtime）；343–349 构建/安装；510–518 静态库和 libLLVM 文件归属。

**没有 TensorFlow、TensorFlow Lite 或 tensorflow-devel 的 BuildRequires。** `python3/python3-devel` 是通用构建依赖，不表示当前 override 路径需安装 TensorFlow Python。
没有单独安装模型 `.pb`/`.tflite` 的命令；模型和 runtime 原生对象进入 LLVM 库，普通 CMake install 与 `%files static-devel`/`%files -n libllvm` 管理最终库；spec 明确检查 `libtf_xla_runtime.a` 不单独安装。

<details>
<summary>展开完整 llvm.spec 原文</summary>

```spec
%define keepstatic 1

# MLGO AOT support for LLVM MLGO (Ahead-of-Time compilation)
# TODO: switch back to a project_config-controlled macro after MLGO is enabled
# for all required arches.
# %%bcond_with mlgo
%ifarch armv7l aarch64 x86_64
%bcond_without mlgo
%endif

%if %{defined _toolchain}
%define _toolchain_override clang
%define llvm_release_build 0
%else
%define llvm_release_build 1
%endif

%define llvm_version 22

%define sdk_install_prefix /home/owner/share/tmp/sdk_tools/lldb
%define sdk_bin_dir %{sdk_install_prefix}/bin
%define sdk_lib_dir %{sdk_install_prefix}/%{_lib}

%if 0%{llvm_release_build}
# Disable debug packages building
%define debug_package %{nil}
%define __debug_install_post %{_rpmconfigdir}/find-debuginfo.sh %{?_find_debuginfo_opts} %{?_find_debuginfo_strip_opts} %{?_find_debuginfo_ko_strip_opts} "%{_builddir}/%{?buildsubdir}"\
	rm -rf "%{buildroot}/usr/lib/debug"\
	rm -rf "%{buildroot}/usr/src/debug"
%endif

Name:      llvm
Summary:   The LLVM Project is a collection of modular and reusable compiler and toolchain technologies
Version:   22.1.8
Release:   1
Group:     Development/Toolchain
License:   NCSA
Source0:   %{name}-%{version}.tar.gz
Source1001: llvm.manifest

# Bundled MLGO AOT assets for the inliner and regalloc models.
# These override build-time AOT compilation, avoiding the need for TensorFlow
# Python in GBS.
Source1002: mlgo_arm_model.tar.gz
Source1003: mlgo_aarch_model.tar.gz
Source1004: mlgo_x86_model.tar.gz

%{!?mlgo_build_jobs: %define mlgo_build_jobs 6}
%{!?mlgo_verify_configure_only: %define mlgo_verify_configure_only 0}

BuildRequires: cmake
BuildRequires: python3
BuildRequires: python3-devel
BuildRequires: patchelf
BuildRequires: binutils-devel
BuildRequires: libxml2-devel
%if 0%{llvm_release_build}
BuildRequires: sed
%endif
BuildRequires: ninja


Requires: libllvm = %{version}-%{release}

%description
LLVM is a compiler infrastructure designed for compile-time, link-time, runtime,
and idle-time optimization of programs from arbitrary programming languages.
LLVM is written in C++ and has been developed since 2000 at the University of
Illinois and Apple. It currently supports compilation of C and C++ programs,
using front-ends derived from GCC 4.0.1. A new front-end for the C family of
languages is in development. The compiler infrastructure
includes mirror sets of programming tools as well as libraries with equivalent
functionality.

%package devel
Summary: Libraries and Header Files for LLVM %{version}
Requires: %{name} = %{version}

%description devel
This package contains library and header files needed to develop
new native programs that use the LLVM infrastructure.

%package static-devel
Summary: Static libraries for LLVM
Requires: %{name} = %{version}

%description static-devel
This package contains static libraries needed to develop new
native programs that use the LLVM infrastructure.

%package -n libllvm
Summary: LLVM shared libraries

%description -n libllvm
Shared libraries for the LLVM compiler infrastructure.

%package -n clang
Summary: Clang %{version} (C Language family frontend for LLVM)
License: NCSA
Requires: llvm = %{version}-%{release}
Provides: libclang.so.%{version}

%description -n clang
A new front-end for the C family of languages is in development.

%package -n clang-devel
Summary: Clang %{version} Development Library
Requires: clang = %{version}-%{release}

%description -n clang-devel
This package contains the clang (C language) frontend for LLVM.
(development files)

%package -n lldb
Summary: LLDB
License: NCSA

%description -n lldb
LLDB is a next generation, high-performance debugger. It is built as a set
of reusable components which highly leverage existing libraries in the
larger LLVM Project, such as the Clang expression parser and LLVM
disassembler.

%package -n lldb-devel
Summary: Development header files for LLDB
Requires: lldb = %{version}-%{release}

%description -n lldb-devel
The package contains header files for the LLDB debugger.

%package -n compiler-rt
Summary: Compiler runtime libraries

%description -n compiler-rt
Compiler runtime libraries

%package -n libomp
Summary:    OpenMP runtime

%description -n libomp
OpenMP runtime.

%package -n libomp-devel
Summary:    Development files for the OpenMP runtime

%description -n libomp-devel
Development files for the OpenMP runtime.

%package -n python-clang
Summary: Python bindings to parts of the Clang library

%description -n python-clang
Python bindings to parts of the Clang library

%prep
%setup -q
%if %{with mlgo}
mkdir -p mlgo_verify_assets
%ifarch armv7l
tar -C mlgo_verify_assets -xzf %{SOURCE1002}
%endif
%ifarch aarch64
tar -C mlgo_verify_assets -xzf %{SOURCE1003}
%endif
%ifarch x86_64
tar -C mlgo_verify_assets -xzf %{SOURCE1004}
%endif
%endif

%build
%if 0%{llvm_release_build}
# Not to build debug info
RELCFLAGS=$(echo $CFLAGS | sed -e 's*\(^\|[[:space:]]\)-g\([[:digit:]]\+\|gdb\|dwarf-[[:digit:]]\)\?* *g')
export CFLAGS=${RELCFLAGS}
RELCXXFLAGS=$(echo $CXXFLAGS | sed -e 's*\(^\|[[:space:]]\)-g\([[:digit:]]\+\|gdb\|dwarf-[[:digit:]]\)\?* *g')
export CXXFLAGS=${RELCXXFLAGS}
RELFFLAGS=$(echo $FFLAGS | sed -e 's*\(^\|[[:space:]]\)-g\([[:digit:]]\+\|gdb\)|dwarf-[[:digit:]]\\?* *g')
export FFLAGS=${RELFFLAGS}
%endif

cp %{SOURCE1001} .
%{?asan:%gcc_unforce_options}

%ifarch armv7l
export QEMU_RESERVED_VA=0x100000000
%endif

# Set up MLGO AOT model paths from bundled verify assets
%if %{with mlgo}
MLGO_AOT_DIR="$PWD/mlgo_verify_assets"
MLGO_BUILD_DIR="$PWD/build"
MLGO_RUNTIME_OBJECTS="${MLGO_AOT_DIR}/xla_runtime_objects/xla_compiled_cpu_function.cc.o;${MLGO_AOT_DIR}/xla_runtime_objects/cpu_function_runtime.cc.o;${MLGO_AOT_DIR}/xla_runtime_objects/custom_call_status.cc.o;${MLGO_AOT_DIR}/xla_runtime_objects/executable_run_options.cc.o;${MLGO_AOT_DIR}/xla_runtime_objects/runtime_single_threaded_matmul_f32.cc.o"
MLGO_REQUIRED_RUNTIME_OBJECTS="xla_compiled_cpu_function.cc.o cpu_function_runtime.cc.o custom_call_status.cc.o executable_run_options.cc.o runtime_single_threaded_matmul_f32.cc.o"
%endif

mkdir -p build
cd build
cmake \
    -G Ninja \
    -DTIZEN=1 \
    -DCMAKE_C_COMPILER=%__cc \
    -DCMAKE_CXX_COMPILER=%__cxx \
    -DLLVM_HOST_TRIPLE=%{_host} \
    -DLLVM_DEFAULT_TARGET_TRIPLE=%{_host} \
    -DLLVM_TARGET_TRIPLE_ENV=%{_host} \
    -DCMAKE_ASM_FLAGS="$CFLAGS" \
    -DCMAKE_C_FLAGS="$CFLAGS" \
    -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
%if %{defined _toolchain}
    -DCMAKE_SHARED_LINKER_FLAGS="-fuse-ld=lld -ffunction-sections -fdata-sections -Wl,--gc-sections" \
    -DCMAKE_EXE_LINKER_FLAGS="-fuse-ld=lld -ffunction-sections -fdata-sections -Wl,--gc-sections" \
    -DLLVM_USE_LINKER=lld \
%endif
    -DLLVM_ENABLE_ASSERTIONS=No \
    -DLLVM_ENABLE_RTTI=ON \
%ifarch x86_64 i686
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD='X86;ARM;AArch64;BPF' \
%endif
%ifarch armv7l
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -DLLVM_TARGETS_TO_BUILD='ARM;BPF' \
    -DLLVM_TARGET_ARCH="ARM" \
%endif
%ifarch aarch64
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD='AArch64;BPF' \
    -DLLVM_TARGET_ARCH="AArch64" \
%endif
%ifarch riscv64
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD='RISCV;BPF' \
%endif
    -DCLANG_ENABLE_ARCMT=OFF \
    -DLLVM_BUILD_LLVM_DYLIB=ON \
    -DCLANG_BUILD_CLANG_DYLIB=ON \
%if %{defined _toolchain}
    -DLLVM_LINK_LLVM_DYLIB=ON \
    -DCLANG_LINK_CLANG_DYLIB=ON \
%endif
    -DLLVM_ENABLE_PROJECTS="clang;lldb;clang-tools-extra;lld;compiler-rt;openmp" \
    -DLLVM_ENABLE_PER_TARGET_RUNTIME_DIR=OFF \
    -DLLVM_BUILD_EXAMPLES=OFF \
    -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_BUILD_TESTS=OFF \
    -DLLVM_INCLUDE_TESTS=OFF \
    -DLLVM_ENABLE_DOXYGEN=OFF \
    -DLLVM_BUILD_DOCS=OFF \
    -DLLVM_INCLUDE_DOCS=OFF \
    -DLLVM_OPTIMIZED_TABLEGEN=ON \
    -DCMAKE_INSTALL_PREFIX=%{_prefix} \
    -DLLVM_LIBDIR_SUFFIX=`echo %{_lib} | sed s/lib//g` \
    -DCLANG_RESOURCE_DIR="../%{_lib}/clang/%{llvm_version}" \
    -DLLVM_BINUTILS_INCDIR=/usr/include \
    -DLLVM_PARALLEL_COMPILE_JOBS=6 \
    -DLLVM_PARALLEL_LINK_JOBS=2 \
%if %{with mlgo}
%ifarch armv7l aarch64 x86_64
    -DTENSORFLOW_AOT_PATH="${MLGO_AOT_DIR}/mlgo_sysroot" \
    -DLLVM_MLGO_EXPORT_TF_XLA_RUNTIME=OFF \
    -DLLVM_MLGO_EMBED_TF_XLA_RUNTIME_OBJECTS="${MLGO_RUNTIME_OBJECTS}" \
    -DLLVM_OVERRIDE_MODEL_HEADER_INLINERSIZEMODEL="${MLGO_AOT_DIR}/InlinerSizeModel.h" \
    -DLLVM_OVERRIDE_MODEL_OBJECT_INLINERSIZEMODEL="${MLGO_AOT_DIR}/InlinerSizeModel.o" \
    -DLLVM_OVERRIDE_MODEL_HEADER_REGALLOCEVICTMODEL="${MLGO_AOT_DIR}/RegAllocEvictModel.h" \
    -DLLVM_OVERRIDE_MODEL_OBJECT_REGALLOCEVICTMODEL="${MLGO_AOT_DIR}/RegAllocEvictModel.o" \
%else
    -DLLVM_INLINER_MODEL_PATH=none \
    -DLLVM_RAEVICT_MODEL_PATH=none \
%endif
%else
    -DLLVM_INLINER_MODEL_PATH=none \
    -DLLVM_RAEVICT_MODEL_PATH=none \
%endif
    ../llvm

%if 0%{mlgo_verify_configure_only}
  # ---- configure-only probe: guard against §0 traps; check sentinels, GBS exit code non-0 is expected ----
  # Note: %%build does not guarantee set -e, so each assertion explicitly uses '|| { ...; exit 1; }'
  # Assertion 0: MLGO_BUILD_DIR is correct (fail immediately with clear error if wrong)
  test -f CMakeCache.txt || \
    { echo "FATAL: MLGO_BUILD_DIR wrong (CMakeCache.txt not found in $(pwd))"; exit 1; }
%if %{with mlgo}
  # Assertion 1: override actually took effect (COPYONLY artifacts exist from configure stage)
  test -f lib/Analysis/InlinerSizeModel.h || \
    { echo "FATAL: Missing InlinerSizeModel.h (override not effective, likely trap 1: silent fallback to none)"; exit 1; }
  test -f lib/Analysis/InlinerSizeModel.o || \
    { echo "FATAL: Missing InlinerSizeModel.o (override not effective)"; exit 1; }
  test -f lib/CodeGen/RegAllocEvictModel.h || \
    { echo "FATAL: Missing RegAllocEvictModel.h(regalloc override not effective)"; exit 1; }
  test -f lib/CodeGen/RegAllocEvictModel.o || \
    { echo "FATAL: Missing RegAllocEvictModel.o(regalloc override not effective)"; exit 1; }
  for mlgo_runtime_object in ${MLGO_REQUIRED_RUNTIME_OBJECTS}; do
    test -f "${MLGO_AOT_DIR}/xla_runtime_objects/${mlgo_runtime_object}" || \
        { echo "FATAL: missing MLGO runtime object: ${mlgo_runtime_object}"; exit 1; }
  done
  # Assertion 1b: bundled objects must match the target arch.
%ifarch armv7l
  MLGO_EXPECT_MACHINE="ARM"
%endif
%ifarch aarch64
  MLGO_EXPECT_MACHINE="AArch64"
%endif
%ifarch x86_64
  MLGO_EXPECT_MACHINE="X86-64"
%endif
  for mlgo_obj in lib/Analysis/InlinerSizeModel.o lib/CodeGen/RegAllocEvictModel.o; do
    readelf -h "${mlgo_obj}" | grep -q "Machine:.*${MLGO_EXPECT_MACHINE}" || \
      { echo "FATAL: ${mlgo_obj} arch mismatch (expected ${MLGO_EXPECT_MACHINE})"; exit 1; }
  done
  for mlgo_runtime_object in ${MLGO_REQUIRED_RUNTIME_OBJECTS}; do
    mlgo_obj="${MLGO_AOT_DIR}/xla_runtime_objects/${mlgo_runtime_object}"
    readelf -h "${mlgo_obj}" | grep -q "Machine:.*${MLGO_EXPECT_MACHINE}" || \
      { echo "FATAL: ${mlgo_obj} arch mismatch (expected ${MLGO_EXPECT_MACHINE})"; exit 1; }
  done
  # Assertion 2: did not fall into autogenerate mock. Use && short-circuit: file missing => FATAL, don't let '! grep' pass
  test -f CMakeCache.txt && \
    ! grep -qE 'LLVM_INLINER_MODEL_PATH(:[^=]+)?=autogenerate' CMakeCache.txt || \
    { echo "FATAL: Fell into autogenerate mock or CMakeCache missing (trap 2)"; exit 1; }
  test -f CMakeCache.txt && \
    ! grep -qE 'LLVM_RAEVICT_MODEL_PATH(:[^=]+)?=autogenerate' CMakeCache.txt || \
    { echo "FATAL: regalloc fell into autogenerate mock"; exit 1; }
  # Assertion 3: MLGO runtime is embedded and tf_xla_runtime is not exported.
  grep -q '^LLVM_MLGO_EXPORT_TF_XLA_RUNTIME:BOOL=OFF$' "${MLGO_BUILD_DIR}/CMakeCache.txt" || \
    { echo "FATAL: MLGO TensorFlow runtime export is not disabled"; exit 1; }
  for mlgo_runtime_object in ${MLGO_REQUIRED_RUNTIME_OBJECTS}; do
    grep -q "xla_runtime_objects/${mlgo_runtime_object}" "${MLGO_BUILD_DIR}/CMakeCache.txt" || \
      { echo "FATAL: MLGO runtime object is not embedded: ${mlgo_runtime_object}"; exit 1; }
  done
  cmake --build . --target tf_xla_runtime || \
    { echo "FATAL: tf_xla_runtime build failed"; exit 1; }
  MLGO_PROBE_ROOT="$PWD/mlgo_probe_root"
  rm -rf "${MLGO_PROBE_ROOT}"
  mkdir -p "${MLGO_PROBE_ROOT}"
  DESTDIR="${MLGO_PROBE_ROOT}" cmake --install . \
    --prefix /usr --component tf_xla_runtime --verbose
  ! find "${MLGO_PROBE_ROOT}" -name libtf_xla_runtime.a | grep -q . || \
    { echo "FATAL: tf_xla_runtime archive should not be installed"; exit 1; }
%endif
  echo MLGO_VERIFY_CONFIGURE_PASS
  exit 86
%endif

# Full build using ninja (already in build/ directory after cd build)
ninja -j %{mlgo_build_jobs}

%install
cd build
cmake -DCMAKE_INSTALL_PREFIX=%{buildroot}/usr -P cmake_install.cmake
ln -sf %{_prefix}/bin/clang++ %{buildroot}%{_prefix}/bin/clang++-%{llvm_version}

ln -sf clang %{buildroot}%{_prefix}/bin/%{_host}-clang
ln -sf clang++ %{buildroot}%{_prefix}/bin/%{_host}-clang++
# Use host triple and resource dir by default via <lang>.cfg
cat >> %{buildroot}/%{_prefix}/bin/clang.cfg << EOF
-target %{_host}
-resource-dir %{_prefix}/%{_lib}/clang/%{llvm_version}
EOF
ln -sf clang.cfg %{buildroot}/%{_prefix}/bin/clang++.cfg

# copy lldb for sdk
mkdir -p %{buildroot}%{sdk_bin_dir}
mkdir -p %{buildroot}%{sdk_lib_dir}

mv %{buildroot}%{_prefix}/bin/lldb %{buildroot}%{sdk_bin_dir}
mv %{buildroot}%{_prefix}/bin/lldb-argdumper %{buildroot}%{sdk_bin_dir}
mv %{buildroot}%{_prefix}/bin/lldb-server %{buildroot}%{sdk_bin_dir}

ln -sf %{sdk_bin_dir}/lldb %{buildroot}%{_prefix}/bin/

cp -P %{buildroot}%{_libdir}/liblldb.so* %{buildroot}%{sdk_lib_dir}/

# Install the clang python bits
mkdir -p %{buildroot}%{python3_sitelib}
cp -a ../clang/bindings/python/clang %{buildroot}%{python3_sitelib}/

rm -rf %{buildroot}%{_libdir}/debug/*
rm -rf %{buildroot}/usr/lib/libear/*
rm -rf %{buildroot}/usr/lib/libscanbuild/*

%post -n clang -p /sbin/ldconfig
%postun -n clang -p /sbin/ldconfig

%post -n lldb
echo "plugin load /usr/share/dotnet.tizen/netcoreapp/SOS/libsosplugin.so" > /root/.lldbinit

%files
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_prefix}/bin/analyze-build
%{_prefix}/bin/bugpoint
%{_prefix}/bin/clang-linker-wrapper
%{_prefix}/bin/clang-offload-packager
%{_prefix}/bin/clang-repl
%{_prefix}/bin/intercept-build
%{_prefix}/bin/llc
%{_prefix}/bin/lld
%{_prefix}/bin/ld.lld
%{_prefix}/bin/ld64.lld
%{_prefix}/bin/lld-link
%{_prefix}/bin/wasm-ld
%{_prefix}/bin/lli
%{_prefix}/bin/llvm-ar
%{_prefix}/bin/llvm-as
%{_prefix}/bin/llvm-bcanalyzer
%{_prefix}/bin/llvm-bitcode-strip
%{_prefix}/bin/llvm-c-test
%{_prefix}/bin/llvm-cat
%{_prefix}/bin/llvm-cgdata
%{_prefix}/bin/llvm-ctxprof-util
%{_prefix}/bin/llvm-config
%{_prefix}/bin/llvm-cov
%{_prefix}/bin/llvm-cvtres
%{_prefix}/bin/llvm-cxxdump
%{_prefix}/bin/llvm-cxxfilt
%{_prefix}/bin/llvm-debuginfo-analyzer
%{_prefix}/bin/llvm-debuginfod
%{_prefix}/bin/llvm-debuginfod-find
%{_prefix}/bin/llvm-diff
%{_prefix}/bin/llvm-dis
%{_prefix}/bin/llvm-dlltool
%{_prefix}/bin/llvm-dwarfdump
%{_prefix}/bin/llvm-dwarfutil
%{_prefix}/bin/llvm-dwp
%{_prefix}/bin/llvm-extract
%{_prefix}/bin/llvm-gsymutil
%{_prefix}/bin/llvm-lib
%{_prefix}/bin/llvm-libtool-darwin
%{_prefix}/bin/llvm-link
%{_prefix}/bin/llvm-lto
%{_prefix}/bin/llvm-lto2
%{_prefix}/bin/llvm-mc
%{_prefix}/bin/llvm-ml
%{_prefix}/bin/llvm-ml64
%{_prefix}/bin/llvm-modextract
%{_prefix}/bin/llvm-mt
%{_prefix}/bin/llvm-nm
%{_prefix}/bin/llvm-objdump
%{_prefix}/bin/llvm-opt-report
%{_prefix}/bin/llvm-otool
%{_prefix}/bin/llvm-remarkutil
%{_prefix}/bin/llvm-pdbutil
%{_prefix}/bin/llvm-profdata
%{_prefix}/bin/llvm-profgen
%{_prefix}/bin/llvm-ranlib
%{_prefix}/bin/llvm-readelf
%{_prefix}/bin/llvm-readobj
%{_prefix}/bin/llvm-readtapi
%{_prefix}/bin/llvm-rtdyld
%{_prefix}/bin/llvm-sim
%{_prefix}/bin/llvm-size
%{_prefix}/bin/llvm-split
%{_prefix}/bin/llvm-stress
%{_prefix}/bin/llvm-strings
%{_prefix}/bin/llvm-symbolizer
%{_prefix}/bin/llvm-tblgen
%{_prefix}/bin/llvm-tli-checker
%{_prefix}/bin/llvm-windres
%{_prefix}/bin/llvm-xray
%{_prefix}/bin/offload-arch
%{_prefix}/bin/opt
%{_prefix}/bin/run-clang-tidy
%{_prefix}/bin/sancov
%{_prefix}/bin/sanstats
%{_prefix}/bin/scan-build
%{_prefix}/bin/scan-build-py
%{_prefix}/bin/scan-view
%{_prefix}/bin/verify-uselistorder
%{_prefix}/bin/diagtool
%{_prefix}/bin/dsymutil
%{_prefix}/bin/hmaptool
%{_prefix}/bin/lldb-dap
%{_prefix}/bin/lldb-instr
%{_prefix}/bin/llvm-addr2line
%{_prefix}/bin/llvm-cfi-verify
%{_prefix}/bin/llvm-cxxmap
%{_prefix}/bin/llvm-exegesis
%{_prefix}/bin/llvm-ifs
%{_prefix}/bin/llvm-install-name-tool
%{_prefix}/bin/llvm-jitlink
%{_prefix}/bin/llvm-lipo
%{_prefix}/bin/llvm-mca
%{_prefix}/bin/llvm-objcopy
%{_prefix}/bin/llvm-rc
%{_prefix}/bin/llvm-reduce
%{_prefix}/bin/llvm-strip
%{_prefix}/bin/llvm-undname
%{_prefix}/bin/pp-trace
%{_prefix}/bin/reduce-chunk-list
%{_prefix}/bin/llvm-cas
%{_prefix}/bin/llvm-ir2vec
%{_prefix}/bin/llvm-offload-binary
%{_prefix}/bin/llvm-offload-wrapper
%{_prefix}/bin/yaml2macho-core

%files devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_prefix}/include/lld/*
%{_prefix}/include/llvm/*
%{_prefix}/include/llvm-c/*
%{_prefix}/share/*
%{_libdir}/cmake/lld/*
%{_libdir}/cmake/llvm/*
%{_libdir}/libLTO*.so*
%{_libdir}/LLVMgold.so
%{_libdir}/libRemarks.so*
%{_prefix}/bin/amdgpu-arch
%{_prefix}/bin/nvptx-arch

%files static-devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_libdir}/lib*.a

%files -n libllvm
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_libdir}/libLLVM*.so*

%files -n clang
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_prefix}/bin/clang
%{_prefix}/bin/clang++
%{_prefix}/bin/%{_host}-clang
%{_prefix}/bin/%{_host}-clang++
%{_prefix}/bin/clang-%{llvm_version}
%{_prefix}/bin/clang++-%{llvm_version}
%{_prefix}/bin/clang-apply-replacements
%{_prefix}/bin/clang-change-namespace
%{_prefix}/bin/clang-check
%{_prefix}/bin/clang-cl
%{_prefix}/bin/clang-cpp
%{_prefix}/bin/clang-doc
%{_prefix}/bin/clang-extdef-mapping
%{_prefix}/bin/clang-move
%{_prefix}/bin/clang-refactor
%{_prefix}/bin/clang-scan-deps
%{_prefix}/bin/clang-format
%{_prefix}/bin/clang-include-cleaner
%{_prefix}/bin/clang-include-fixer
%{_prefix}/bin/clang-offload-bundler
%{_prefix}/bin/clang-query
%{_prefix}/bin/clang-sycl-linker
%{_prefix}/bin/clang-reorder-fields
%{_prefix}/bin/clang-tidy
%{_prefix}/bin/clang-installapi
%{_prefix}/bin/clang-nvlink-wrapper
%{_prefix}/bin/clangd
%{_prefix}/bin/git-clang-format
%{_prefix}/bin/find-all-symbols
%{_prefix}/bin/modularize
%{_libdir}/clang/%{llvm_version}/include/*
%{_libdir}/libclang*.so*
%{_libdir}/cmake/clang/*
%{_prefix}/libexec/analyze-c++
%{_prefix}/libexec/analyze-cc
%{_prefix}/libexec/c++-analyzer
%{_prefix}/libexec/ccc-analyzer
%{_prefix}/libexec/intercept-c++
%{_prefix}/libexec/intercept-cc
%{_prefix}/bin/clang.cfg
%{_prefix}/bin/clang++.cfg

%files -n clang-devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_prefix}/bin/clang-tblgen
%{_prefix}/include/clang/*
%{_prefix}/include/clang-c/*
%{_prefix}/include/clang-tidy/*

%files -n lldb
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{sdk_bin_dir}/lldb
%{_prefix}/bin/lldb
%{sdk_bin_dir}/lldb-argdumper
%{sdk_bin_dir}/lldb-server
%{sdk_lib_dir}/liblldb*.so*
%{_prefix}/bin/lldb-mcp

%files -n lldb-devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_prefix}/include/lldb/*
%{_libdir}/liblldb*.so*
%{_prefix}/bin/lldb-tblgen

%files -n compiler-rt
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_libdir}/clang/%{llvm_version}/include/sanitizer/*
%{_libdir}/clang/%{llvm_version}/*

%files -n libomp
%{_libdir}/libomp.so
%ifnarch %arm
%{_libdir}/libompd.so
%{_libdir}/libarcher.so
%endif

%files -n libomp-devel
%ifnarch %arm
%{_libdir}/libarcher_static.a
%endif
%{_libdir}/cmake/openmp/FindOpenMPTarget.cmake

%files -n python-clang
%{python3_sitelib}/clang
```

</details>

## 复现与发布边界

在本地工作目录已执行的关键步骤：

```sh
git clone git://review.tizen.org/git/platform/upstream/llvm -b tizen_base llvm-tizen
git -C llvm-tizen log --oneline --no-merges llvmorg-22.1.8..tizen_base > commits_all.txt
git -C llvm-tizen format-patch llvmorg-22.1.8..tizen_base -o ../patches_all/
git -C llvm-tizen worktree add ../llvm-22 llvmorg-22.1.8
# 从 patches_all 按原 SHA 复制选中项到 patches_mlgo，之后按编号逐个：
git -C llvm-22 am -3 /absolute/path/to/patches_mlgo/NNNN-xxx.patch
# 失败：记录日志/冲突片段后执行
git -C llvm-22 am --skip
```

没有重写 llvm-tizen 已有提交或移动 tizen_base；新提交只产生在用户指定的临时 llvm-22 worktree。
源分支 HEAD 最终仍是 `f999bd406c0a70fe8107aa992164fe6945c5d46a`，工作区干净。
本地 `packaging_tizen_base/` 的所有文件与源 packaging 逐字节一致。

发布目标仅为新建私有仓库 `lhmax2010/tizen-llvm-mlgo-port`，只推送报告、清单、可发布补丁、文本 packaging 副本及 `.gitignore`。
源码目录、全部原始补丁目录、临时脚本/日志、模型压缩包、107 MiB 原始 0001 及解包证据均不推送；不向其他仓库推送，也不创建 PR。
