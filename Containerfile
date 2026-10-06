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

# ---- Stage 3: the image
FROM ${BASE}
ARG KVER
COPY --from=kmods /out/ /
COPY image/rootfs/ /
RUN set -eux; \
    test "$(ls /usr/lib/modules)" = "$KVER"; \
    depmod -a "$KVER"; \
    for m in ov8865 ov5693 nxp_nci nxp_nci_i2c intel_hid; do \
        modinfo -k "$KVER" -F filename "$m" | grep -q '/updates/' || { echo "$m does not resolve to updates/"; exit 1; }; \
    done
# Plymouth's configuration is copied into the initramfs: regenerate it so image/rootfs/etc/plymouth/plymouthd.conf takes effect.
RUN set -eux; \
    DRACUT_NO_XATTR=1 dracut --no-hostonly --kver "$KVER" --reproducible --add ostree -f "/usr/lib/modules/$KVER/initramfs.img"; \
    chmod 0600 "/usr/lib/modules/$KVER/initramfs.img"
LABEL org.opencontainers.image.title="Surface Overdrive" \
      org.opencontainers.image.source="https://github.com/ccccri/surface-overdrive"
