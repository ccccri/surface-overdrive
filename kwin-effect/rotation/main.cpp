/*
    SPDX-FileCopyrightText: 2021 Vlad Zahorodnii <vlad.zahorodnii@kde.org>
    SPDX-FileCopyrightText: 2026 ccccri

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#include "rotation.h"

namespace KWin
{

KWIN_EFFECT_FACTORY_SUPPORTED(OverdriveRotationEffect,
                              "metadata.json",
                              return OverdriveRotationEffect::supported();)

} // namespace KWin

#include "main.moc"
