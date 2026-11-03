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
