# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-09-09
### Added
- Initial release of DataRecovery application
- GTK4/Libadwaita-based user interface for data recovery
- Integration with ddrescue for disk recovery operations
- Integration with PhotoRec for file recovery
- File organization by type after recovery
- Duplicate file detection and removal using rdfind
- Support for both storage devices and disk images
- Polkit integration for elevated permissions when needed
- Desktop application with proper .desktop file and icons
- Meson build system integration
- Python 3 application with GTK4 bindings

### Packaging
- Initial package for openSUSE Build Service
- Fixed rpmlint issues: removed explicit libadwaita dependency, added changelog
