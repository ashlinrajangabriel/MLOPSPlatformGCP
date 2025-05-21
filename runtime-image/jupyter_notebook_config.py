c = get_config()  # noqa

# Basic configuration
c.NotebookApp.ip = '0.0.0.0'
c.NotebookApp.port = 8888
c.NotebookApp.open_browser = False
c.NotebookApp.token = ''
c.NotebookApp.password = ''
c.NotebookApp.allow_origin = '*'
c.NotebookApp.allow_remote_access = True

# Enable JupyterLab by default
c.NotebookApp.default_url = '/lab'

# Terminal configuration
c.TerminalInteractiveShell.term_title = True
c.TerminalInteractiveShell.confirm_exit = False

# Kernel configuration
c.MultiKernelManager.default_kernel_name = 'python3'

# File locations
c.NotebookApp.notebook_dir = '/home/jovyan/workspace'

# Security settings (since we're using JupyterHub for auth)
c.NotebookApp.disable_check_xsrf = False
c.NotebookApp.allow_root = False

# Extension configuration
c.NotebookApp.nbserver_extensions = {
    'jupyterlab': True,
}

# Collaboration tools
c.NotebookApp.collaborative = True

# Resource usage
c.NotebookApp.ResourceUseDisplay.track_cpu_percent = True
c.NotebookApp.ResourceUseDisplay.track_memory_usage = True 