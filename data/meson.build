install_data('datarecovery.desktop.in',
  install_dir: get_option('datadir') / 'applications',
  rename: 'datarecovery.desktop')

install_data('datarecovery.policy',
  install_dir: get_option('datadir') / 'polkit-1' / 'actions')

desktop_utils = find_program('desktop-file-validate', required: false)
if desktop_utils.found()
  test('Validate desktop file', desktop_utils, args: ['datarecovery.desktop.in'])
endif

subdir('icons')
