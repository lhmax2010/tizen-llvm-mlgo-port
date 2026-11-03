%define llvm_major 22
%define llvm_version 22.1.8

Name:           libcxx-runtimes
Version:        22.1.8
Release:        1
ExclusiveArch:  armv7l aarch64 x86_64
Summary:        LLVM libc++ and libc++abi runtimes
Group:          Development/Toolchain
License:        Apache-2.0 WITH LLVM-exception
URL:            https://llvm.org/
Source0:        llvm-%{version}.tar.gz
Source1:        libcxx-llvm22.map
Source2:        libcxx-runtimes.manifest
Source3:        SOURCE_PROVENANCE

BuildRequires:  clang = %{version}
BuildRequires:  cmake
BuildRequires:  ninja
BuildRequires:  python3
BuildRequires:  glibc-devel
BuildRequires:  libgcc

%description
Source package for the LLVM libc++ standard library and libc++abi runtime.
The libraries use libgcc_s as the unwinder and export only default-version
LLVM_22 symbols.

%package -n libc++
Summary:        LLVM C++ standard library runtime
Requires:       libc++abi = %{version}-%{release}

%description -n libc++
Shared LLVM libc++ runtime, built against libc++abi and libgcc_s.

%package -n libc++-devel
Summary:        LLVM C++ standard library headers and development files
Requires:       libc++ = %{version}-%{release}
Requires:       libc++abi-devel = %{version}-%{release}

%description -n libc++-devel
Headers, ABI linker script, module metadata, and development files for LLVM
libc++.

%package -n libc++abi
Summary:        LLVM C++ ABI runtime

%description -n libc++abi
Shared LLVM libc++abi runtime using libgcc_s rather than LLVM libunwind.

%package -n libc++abi-devel
Summary:        LLVM C++ ABI development files
Requires:       libc++abi = %{version}-%{release}

%description -n libc++abi-devel
Linker name for LLVM libc++abi.  Its public headers are installed in the
common c++/v1 tree shipped by libc++-devel.

%prep
%setup -q -n llvm-%{version}
cp %{SOURCE2} .
cp %{SOURCE3} .

%build
%ifarch aarch64
CFLAGS="$(printf '%%s\n' "$CFLAGS" | sed 's/-mtune=cortex-a57\.cortex-a53/-mtune=cortex-a53/g')"
CXXFLAGS="$(printf '%%s\n' "$CXXFLAGS" | sed 's/-mtune=cortex-a57\.cortex-a53/-mtune=cortex-a53/g')"
export CFLAGS CXXFLAGS
%endif

mkdir -p build
cd build

cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=%{_host}-clang \
  -DCMAKE_CXX_COMPILER=%{_host}-clang++ \
  -DCMAKE_ASM_COMPILER=%{_host}-clang \
  -DCMAKE_C_COMPILER_TARGET=%{_host} \
  -DCMAKE_CXX_COMPILER_TARGET=%{_host} \
  -DCMAKE_ASM_COMPILER_TARGET=%{_host} \
  -DCMAKE_C_FLAGS="$CFLAGS --rtlib=libgcc" \
  -DCMAKE_CXX_FLAGS="$CXXFLAGS --rtlib=libgcc" \
  -DCMAKE_ASM_FLAGS="$CFLAGS" \
  -DCMAKE_SHARED_LINKER_FLAGS="-Wl,--version-script=%{SOURCE1} -Wl,-z,now --rtlib=libgcc" \
  -DCMAKE_EXE_LINKER_FLAGS="--rtlib=libgcc" \
  -DCMAKE_INSTALL_PREFIX=%{_prefix} \
  -DCMAKE_INSTALL_LIBDIR=%{_lib} \
  -DLIBCXX_INSTALL_LIBRARY_DIR=%{_lib} \
  -DLIBCXXABI_INSTALL_LIBRARY_DIR=%{_lib} \
  -DLLVM_ENABLE_RUNTIMES="libcxxabi;libcxx" \
  -DLLVM_DEFAULT_TARGET_TRIPLE=%{_host} \
  -DLLVM_INCLUDE_TESTS=OFF \
  -DLIBCXX_ENABLE_SHARED=ON \
  -DLIBCXX_ENABLE_STATIC=OFF \
  -DLIBCXX_INSTALL_SHARED_LIBRARY=ON \
  -DLIBCXX_INSTALL_STATIC_LIBRARY=OFF \
  -DLIBCXX_CXX_ABI=libcxxabi \
  -DLIBCXX_ENABLE_STATIC_ABI_LIBRARY=OFF \
  -DLIBCXX_ENABLE_ABI_LINKER_SCRIPT=ON \
  -DLIBCXX_USE_COMPILER_RT=OFF \
  -DLIBCXXABI_ENABLE_SHARED=ON \
  -DLIBCXXABI_ENABLE_STATIC=OFF \
  -DLIBCXXABI_INSTALL_SHARED_LIBRARY=ON \
  -DLIBCXXABI_INSTALL_STATIC_LIBRARY=OFF \
  -DLIBCXXABI_USE_COMPILER_RT=OFF \
  -DLIBCXXABI_USE_LLVM_UNWINDER=OFF \
  -DLIBCXXABI_ENABLE_STATIC_UNWINDER=OFF \
  -DLIBCXXABI_STATICALLY_LINK_UNWINDER_IN_SHARED_LIBRARY=OFF \
  -DLIBCXXABI_STATICALLY_LINK_UNWINDER_IN_STATIC_LIBRARY=OFF \
  -DLIBCXXABI_ENABLE_NEW_DELETE_DEFINITIONS=ON \
  -DLIBCXX_INCLUDE_TESTS=OFF \
  -DLIBCXXABI_INCLUDE_TESTS=OFF \
  -DLIBCXX_INCLUDE_BENCHMARKS=OFF \
  ../runtimes

cmake --build . --target cxxabi cxx cxx_experimental %{?_smp_mflags}

%install
cd build
DESTDIR=%{buildroot} cmake --install .

install -d %{buildroot}%{_datadir}/doc/%{name}
install -m 0644 ../SOURCE_PROVENANCE \
  %{buildroot}%{_datadir}/doc/%{name}/SOURCE_PROVENANCE

%files -n libc++
%manifest %{name}.manifest
%defattr(-,root,root,-)
%license libcxx/LICENSE.TXT
%{_libdir}/libc++.so.1*

%files -n libc++-devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_includedir}/c++/v1
%{_libdir}/libc++.so
%{_libdir}/libc++experimental.a
%{_libdir}/libc++.modules.json
%{_datadir}/libc++/v1
%{_datadir}/doc/%{name}/SOURCE_PROVENANCE

%files -n libc++abi
%manifest %{name}.manifest
%defattr(-,root,root,-)
%license libcxxabi/LICENSE.TXT
%{_libdir}/libc++abi.so.1*

%files -n libc++abi-devel
%manifest %{name}.manifest
%defattr(-,root,root,-)
%{_libdir}/libc++abi.so

%changelog
* Tue Aug 04 2026 Toolchain ABI Team <toolchain@example.invalid> 22.1.8-1
- Migrate to the verbatim platform llvm-22.1.8 source tarball and LLVM_22 symbol node.
- Preserve the adjudicated 21.1.1 multi-architecture packaging decisions.

* Sat Jul 25 2026 Toolchain ABI Team <toolchain@example.invalid> 21.1.1-2
- Build armv7l, aarch64, and x86_64 repository-candidate runtimes.

* Thu Jul 23 2026 Toolchain ABI Team <toolchain@example.invalid> 21.1.1-1
- Initial armv7l PoC packaging with LLVM_21 default symbol versions.