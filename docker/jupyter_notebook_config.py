# Configuration file for jupyter-notebook.

## Set the Access-Control-Allow-Origin header
#  
#  Use '*' to allow any origin to access your server.
#  
#  Takes precedence over allow_origin_pat.
c.NotebookApp.allow_origin = '*'

## The IP address the notebook server will listen on.
c.NotebookApp.ip = '*'

## The directory to use for notebooks and kernels.
c.NotebookApp.notebook_dir = '/asilinks_server/notebooks'

## Whether to open in a browser after starting. The specific browser used is
#  platform dependent and determined by the python standard library `webbrowser`
#  module, unless it is overridden using the --browser (NotebookApp.browser)
#  configuration option.
c.NotebookApp.open_browser = False

## Hashed password to use for web authentication.
#  
#  To generate, type in a python/IPython shell:
#  
#    from notebook.auth import passwd; passwd()
#  
#  The string should be of the form type:salt:hashed-password.
c.NotebookApp.password = 'sha1:03fd58034994:551e16039b23a95ebe7558b8c9e92c2bab6b1e65'

## The port the notebook server will listen on.
c.NotebookApp.port = 8888
