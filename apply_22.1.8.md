# MLGO patches 在 llvmorg-22.1.8 上的顺序试打

- 起点：`llvmorg-22.1.8` (`ca7933e47d3a3451d81e72ac174dcb5aa28b59d1`)。
- 按 patches_mlgo 文件名编号顺序逐个执行 `git am -3 <patch>`；失败即记录并执行 `git am --skip`。不手工解决，不启用 rerere。
- “干净”包含 Git 自动三方合并成功；仅表示可应用，不代表可编译或行为正确。
- “有冲突”项记录后已跳过；后续 patch 基于前面成功应用的累积结果，可能受到跳过依赖项的影响。
- “跳过”仅用于 Git 报告已经应用或无需变更的情况。
- 本次使用本地原始完整补丁（0001 包含模型包），不是 GitHub 的 `code_only/0001`；后者仅为发布时排除模型载荷的替代文件。
- 候选共 5 个：0001/0007 为明确 MLGO，0011/0013/0014 为仅间接构建关联的“待确认”项。

| Patch | 原提交 | 结果 | 冲突文件 |
|---|---|---|---|
| 0001-Add-packaging.patch | `3d723549f603` | 干净 | — |
| 0007-Merge-MLGO-AOT-compilation-support-and-optimization-.patch | `fd7a4929c0e4` | 干净 | — |
| 0011-optimize-llvm-performance.patch | `7e4dc62d8ac0` | 干净 | — |
| 0013-packaging-fix-llvm-static-devel-with-ThinLTO.patch | `67619ec8bbba` | 干净 | — |
| 0014-Revert-clang-bootstrap-ThinLTO-fall-back-to-GCC.patch | `f999bd406c0a` | 有冲突 | `packaging/llvm.spec` |

统计：干净 4；有冲突 1；跳过 0。

操作统计：成功生成 4 个提交；因冲突执行 `git am --skip` 1 次；因为已存在/空变更而跳过 0 次。两个明确 MLGO 补丁均干净。

## 0001-Add-packaging.patch

原提交：`3d723549f6037bdab5be47aaa6e6354fd3707d89`；结果：**干净**。

```text
Applying: Add packaging
```

## 0007-Merge-MLGO-AOT-compilation-support-and-optimization-.patch

原提交：`fd7a4929c0e424d564cdd1f0c55af9153dcea321`；结果：**干净**。

```text
Applying: Merge MLGO AOT compilation support and optimization improvements
```

## 0011-optimize-llvm-performance.patch

原提交：`7e4dc62d8ac01f90488a0cc8e0f34f8373228c84`；结果：**干净**。

```text
Applying: optimize llvm performance 1. Use -O3 2. Using thin-lto 3. Static link libllvm
```

## 0013-packaging-fix-llvm-static-devel-with-ThinLTO.patch

原提交：`67619ec8bbbac7238a6cfc33a481ccfbcd12206f`；结果：**干净**。

```text
Applying: packaging: fix llvm-static-devel with ThinLTO
```

## 0014-Revert-clang-bootstrap-ThinLTO-fall-back-to-GCC.patch

原提交：`f999bd406c0a70fe8107aa992164fe6945c5d46a`；结果：**有冲突**。

```text
Applying: Revert clang bootstrap + ThinLTO, fall back to GCC
Using index info to reconstruct a base tree...
M	packaging/llvm.spec
Falling back to patching base and 3-way merge...
Auto-merging packaging/llvm.spec
CONFLICT (content): Merge conflict in packaging/llvm.spec
Removing packaging/llvm-static-archives-native.py
error: Failed to merge in the changes.
hint: Use 'git am --show-current-patch=diff' to see the failed patch
Patch failed at 0001 Revert clang bootstrap + ThinLTO, fall back to GCC
When you have resolved this problem, run "git am --continue".
If you prefer to skip this patch, run "git am --skip" instead.
To restore the original branch and stop patching, run "git am --abort".
```

### `packaging/llvm.spec`

```diff
<<<<<<< HEAD
%ifarch x86_64
# Strip pre-existing optimization flags and remove performance-harming flags, then force -O3 + ThinLTO
OPTFLAGS_CFLAGS=$(echo "$CFLAGS" | sed \
    -e 's/\-O[0-9sz]//g' \
    -e 's/\-Ofast//g' \
    -e 's/\-fstack-protector-strong//g' \
    -e 's/\-fstack-protector-all//g' \
    -e 's/\-fstack-protector//g' \
    -e 's/\-fno-omit-frame-pointer//g' \
    -e 's/\-momit-leaf-frame-pointer//g')
OPTFLAGS_CXXFLAGS=$(echo "$CXXFLAGS" | sed \
    -e 's/\-O[0-9sz]//g' \
    -e 's/\-Ofast//g' \
    -e 's/\-fstack-protector-strong//g' \
    -e 's/\-fstack-protector-all//g' \
    -e 's/\-fstack-protector//g' \
    -e 's/\-fno-omit-frame-pointer//g' \
    -e 's/\-momit-leaf-frame-pointer//g')
export CFLAGS="$OPTFLAGS_CFLAGS -O3 -flto=thin -fomit-frame-pointer -Wno-unused-command-line-argument"
export CXXFLAGS="$OPTFLAGS_CXXFLAGS -O3 -flto=thin -fomit-frame-pointer -Wno-unused-command-line-argument"
%endif

=======
>>>>>>> Revert clang bootstrap + ThinLTO, fall back to GCC
```


未合并索引（stage 1=原基线，2=目标 worktree，3=补丁侧）：

```text
100644 8240282641a3afad12370eb7d03af57b7c4e9c13 1	packaging/llvm.spec
100644 c2883341a48fe00c9102718de3296346ba464df4 2	packaging/llvm.spec
100644 c901dc5a2d5d36dcc9006a037ebaed1809c1a3a4 3	packaging/llvm.spec
```

`git am --skip`：成功。

原因初判：未纳入的通用补丁 `0012`（`cb67996861d0`）给这个 block 增加两条 `-fno-inline-functions` 过滤规则，0014 的父版本包含它们；试打子集不包含它们。0014 删除整个 block 时出现三方文本冲突。此处是通用构建参数历史不完整，不是 MLGO advisor/API 在 22.1.8 上的冲突。

结束 HEAD：`5f72a1a1fa4e55526e71d525f45db456134bc01d`。

结束工作区状态：干净。
