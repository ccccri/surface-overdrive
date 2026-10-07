cmake_minimum_required(VERSION 3.20)
project(overdrive_kcm VERSION 0.1 LANGUAGES CXX)

find_package(ECM REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

# Qt6 first: KDEInstallDirs picks the Qt version from what is already found
find_package(Qt6 REQUIRED COMPONENTS Core Qml Quick)
find_package(KF6 REQUIRED COMPONENTS CoreAddons I18n KCMUtils)

include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

kcmutils_add_qml_kcm(kcm_overdrive SOURCES overdrivekcm.cpp overdrivekcm.h)
target_link_libraries(kcm_overdrive PRIVATE Qt6::Core Qt6::Qml Qt6::Quick KF6::CoreAddons KF6::I18n KF6::KCMUtilsQuick)
