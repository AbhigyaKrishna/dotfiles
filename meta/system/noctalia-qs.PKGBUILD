# Maintainer: noctalia-dev <team@noctalia.dev>
pkgname=noctalia-qs
pkgver=0.0.12
pkgrel=2.1
pkgdesc='Custom fork of Quickshell powering Noctalia Shell'
arch=(x86_64 aarch64)
url="https://github.com/noctalia-dev/noctalia-qs"
license=('LGPL-3.0-only')
depends=(
    gcc-libs
    glibc
    hicolor-icon-theme
    jemalloc
    libdrm
    libglvnd
    libpipewire
    libxcb
    mesa
    pam
    qt6-base
    qt6-declarative
    qt6-svg
    qt6-wayland
    wayland
    polkit
)
makedepends=(
    cli11
    cmake
    ninja
    qt6-shadertools
    spirv-tools
    wayland-protocols
    git
    vulkan-headers
)

provides=("quickshell" "quickshell-git")

conflicts=(
    quickshell
    quickshell-git
)
options=(!debug)
_archive="$pkgname-$pkgver"
source=("$_archive.tar.gz::$url/archive/v$pkgver.tar.gz")
sha256sums=('5de37541537307d141618aa0d782d3c34e42a6ad21c73533cce80c0e71ee9693')

build() {
    cd "$_archive"
    local cmake_options=(
        -D CMAKE_BUILD_TYPE=Release
        -D DISTRIBUTOR="Arch Linux"
        -D DISTRIBUTOR_DEBUGINFO_AVAILABLE=Yes
        -D CRASH_REPORTER=Off
        -D CMAKE_INSTALL_PREFIX=/usr
        -D INSTALL_QML_PREFIX=lib/qt6/qml
    )
    cmake -G Ninja -B build -Wno-dev "${cmake_options[@]}"
    cmake --build build
}

package() {
    cd "$_archive"
    DESTDIR="$pkgdir" cmake --install build
    install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}

# Local Qt 6.12 complete-type compatibility patch.
source+=("noctalia-qs-qt612-bindables.patch")
sha256sums+=("9a0f675b918fbd69b2ff1dc17d1e32c30c04c786a1975abb0a3146165a1f9a77")

prepare() {
    cd "$_archive"
    patch -Np1 -i "$srcdir/noctalia-qs-qt612-bindables.patch"
}
