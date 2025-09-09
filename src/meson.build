pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'datarecovery'
gnome = import('gnome')

gnome.compile_resources('datarecovery',
  'datarecovery.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'datarecovery.in',
  output: 'datarecovery',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr-xr-x'
)

datarecovery_sources = [
  '__init__.py',
  'main.py',
  'window.py',
  'about.py',
  'block_devices.py',
  'partition_guids.py',
  'device_columnview.py',
  'image.py',
  'image_helper.py',
  'preflight.py',
  'recover.py',
  'organise_files.py',
  'duplicates.py',
  'log.py',
  'mounted_check.py',
  'application.py',
  'device_dropdown.py',
]

install_data(datarecovery_sources, install_dir: moduledir)
