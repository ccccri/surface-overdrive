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
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Back end shared by every page of the "Surface Control" group
add_library(overdrive_common STATIC common/overdrivekcm.cpp common/overdrivekcm.h common/preview.cpp common/preview.h common/penmonitor.cpp common/penmonitor.h common/nfcmonitor.cpp common/nfcmonitor.h)
target_include_directories(overdrive_common PUBLIC common)
target_link_libraries(overdrive_common PUBLIC Qt6::Core Qt6::Qml Qt6::Quick KF6::CoreAddons KF6::I18n KF6::KCMUtilsQuick)

# One System Settings page = one directory with its own CMakeLists.txt, <plugin>.json, page_<name>.cpp and ui/main.qml
add_subdirectory(overview)
add_subdirectory(pen)
add_subdirectory(cameras)
add_subdirectory(sound)
add_subdirectory(nfc)
add_subdirectory(sensors)
