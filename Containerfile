# Surface Overdrive system image.
#
#   podman build --build-arg BASE=quay.io/fedora-ostree-desktops/kinoite:44 --build-arg KVER=<kernel of BASE> \
#       --secret id=modkey,src=<key.pem> --secret id=modcert,src=<cert.der> -t surface-overdrive:44 .
#
# `ci/detect.sh` prints the build arguments. KVER must be exactly the kernel of BASE (label `ostree.linux`).
ARG BASE=quay.io/fedora-ostree-desktops/kinoite:44

# ---- Stage 1: download the exact kernel sources and headers (cached while KVER does not change)
FROM registry.fedoraproject.org/fedora:44 AS kernel-src
ARG KVER
RUN dnf -y install --setopt=install_weak_deps=False curl cpio rpm xz && dnf clean all
RUN set -eux; \
    ver=${KVER%%-*}; rest=${KVER#*-}; rel=${rest%.*}; arch=${KVER##*.}; \
    base=https://kojipkgs.fedoraproject.org/packages/kernel/$ver/$rel; \
    mkdir -p /dl /srpm; cd /dl; \
    curl -fsSL -O $base/$arch/kernel-devel-$KVER.rpm; \
    curl -fsSL -o kernel.src.rpm $base/src/kernel-$ver-$rel.src.rpm; \
    cd /srpm; rpm2cpio /dl/kernel.src.rpm | cpio -idm --quiet "./linux-$ver.tar.xz" "./patch-*-redhat.patch"; \
    test -s "linux-$ver.tar.xz"; ls patch-*-redhat.patch; \
    rm /dl/kernel.src.rpm

# ---- Stage 2: build and sign the modules
FROM registry.fedoraproject.org/fedora:44 AS kmods
ARG KVER
COPY --from=kernel-src /dl /dl
RUN dnf -y install --setopt=install_weak_deps=False gcc make git kmod openssl elfutils-libelf-devel dwarves python3 /dl/kernel-devel-$KVER.rpm \
    && dnf clean all
COPY --from=kernel-src /srpm /srpm
COPY kmods /src/kmods
COPY patches/kernel /src/patches/kernel
COPY ci/build_kmods.py /src/ci/build_kmods.py
RUN --mount=type=secret,id=modkey --mount=type=secret,id=modcert \
    python3 /src/ci/build_kmods.py --kver "$KVER" --srpm-dir /srpm \
        --key /run/secrets/modkey --cert /run/secrets/modcert --work /work --out /out

# ---- Stage 3: libcamera rebuilt from Fedora's own package with our patches
# The version installed in the base image decides which SRPM is rebuilt (same version = same ABI as the PipeWire plugin).
FROM ${BASE} AS probe
RUN rpm -q --qf '%{VERSION}-%{RELEASE}' libcamera > /libcamera-nvr && rpm -qa --qf '%{NAME}\n' | grep '^libcamera' | sort > /libcamera-packages

FROM registry.fedoraproject.org/fedora:44 AS libcamera
COPY --from=probe /libcamera-nvr /libcamera-packages /
RUN dnf -y install --setopt=install_weak_deps=False rpm-build dnf-plugins-core python3 curl && dnf clean all
COPY ci/build_libcamera.sh /src/ci/build_libcamera.sh
COPY patches/libcamera /src/patches/libcamera
RUN /src/ci/build_libcamera.sh "$(cat /libcamera-nvr)" /src/patches/libcamera /out/rpms

# ---- Stage 4: the image
FROM ${BASE}
ARG KVER
COPY --from=kmods /out/ /
COPY --from=libcamera /out/rpms /tmp/libcamera-rpms
COPY --from=libcamera /libcamera-packages /tmp/libcamera-packages
COPY image/rootfs/ /
COPY src/ /usr/lib/overdrive/python/
RUN set -eux; \
    test "$(ls /usr/lib/modules)" = "$KVER"; \
    depmod -a "$KVER"; \
    for m in ov8865 ov5693 nxp_nci nxp_nci_i2c intel_hid; do \
        modinfo -k "$KVER" -F filename "$m" | grep -q '/updates/' || { echo "$m does not resolve to updates/"; exit 1; }; \
    done
# Replace the stock libcamera packages (only the ones the base image has) with the rebuilt ones.
RUN set -eux; \
    files=""; \
    for name in $(cat /tmp/libcamera-packages); do \
        f=$(ls /tmp/libcamera-rpms/"$name"-[0-9]*.rpm | head -1); files="$files $f"; \
    done; \
    dnf5 -y install --allowerasing $files; \
    rpm -q libcamera libcamera-ipa | grep -q overdrive; \
    rm -rf /tmp/libcamera-rpms /tmp/libcamera-packages; dnf5 clean all
# Plymouth's configuration is copied into the initramfs: regenerate it so image/rootfs/etc/plymouth/plymouthd.conf takes effect.
RUN set -eux; \
    DRACUT_NO_XATTR=1 dracut --no-hostonly --kver "$KVER" --reproducible --add ostree -f "/usr/lib/modules/$KVER/initramfs.img"; \
    chmod 0600 "/usr/lib/modules/$KVER/initramfs.img"
LABEL org.opencontainers.image.title="Surface Overdrive" \
      org.opencontainers.image.source="https://github.com/ccccri/surface-overdrive"
