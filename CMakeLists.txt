cmake_minimum_required(VERSION 3.16)
project(PytroNOVA VERSION 3.9.4 LANGUAGES CXX)

include(GNUInstallDirs)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(QT NAMES Qt6 Qt5 REQUIRED COMPONENTS Widgets)
find_package(Qt${QT_VERSION_MAJOR} REQUIRED COMPONENTS Widgets)

add_executable(PytroNOVA app/main.cpp app/advanced_dialog.cpp app/overlay_workspace.cpp)
target_link_libraries(PytroNOVA PRIVATE Qt${QT_VERSION_MAJOR}::Widgets)

# A Qt/C++ translation unit is large; cap MinGW Release optimizer memory use.
# This is intentionally retained from v3.9.1 for compilation parity.
if(MINGW)
    target_compile_options(PytroNOVA PRIVATE $<$<CONFIG:Release>:-O0> -g0)
endif()
if(WIN32)
    set_target_properties(PytroNOVA PROPERTIES WIN32_EXECUTABLE TRUE)
else()
    # Install a real native executable, not a Wine or Python GUI wrapper.
    install(TARGETS PytroNOVA RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
    install(DIRECTORY backend/ DESTINATION "${CMAKE_INSTALL_DATADIR}/pytro-nova/backend"
            FILES_MATCHING PATTERN "*.py" PATTERN "__pycache__" EXCLUDE)
    install(FILES packaging/linux/pytro-nova.desktop
            DESTINATION "${CMAKE_INSTALL_DATADIR}/applications")
    install(FILES packaging/linux/pytro-nova.svg
            DESTINATION "${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps")
    # Retain the stand-alone converter alongside the backend for offline usage.
    install(PROGRAMS tools/nova_to_txt.py DESTINATION "${CMAKE_INSTALL_DATADIR}/pytro-nova/tools")
    configure_file(packaging/linux/pytro-nova-to-txt.in
                   "${CMAKE_CURRENT_BINARY_DIR}/pytro-nova-to-txt" @ONLY)
    install(PROGRAMS "${CMAKE_CURRENT_BINARY_DIR}/pytro-nova-to-txt"
            DESTINATION "${CMAKE_INSTALL_BINDIR}")
    install(FILES LICENSE THIRD_PARTY_NOTICES.md DESTINATION "${CMAKE_INSTALL_DOCDIR}")
    install(DIRECTORY docs/licenses/ DESTINATION "${CMAKE_INSTALL_DOCDIR}/licenses")
endif()

# Build Debian packages with: cpack -G DEB --config build/CPackConfig.cmake
set(CPACK_PACKAGE_NAME "pytro-nova")
set(CPACK_PACKAGE_VENDOR "Pytro-NOVA contributors")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Offline electrochemical NOVA data explorer and clean text exporter")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Pytro-NOVA maintainers")
set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON)
set(CPACK_DEBIAN_PACKAGE_DEPENDS "python3 (>= 3.9), python3-numpy, python3-scipy")
set(CPACK_DEBIAN_FILE_NAME DEB-DEFAULT)
include(CPack)
