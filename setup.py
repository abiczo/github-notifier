from setuptools import setup
from githubnotifier import __version__

setup(name='github-notifier',
      description='Github updates notifier for Linux',
      author='Andras Biczo',
      author_email='abiczo@gmail.com',
      url='http://github.com/abiczo/github-notifier',
      license='MIT',
      version=__version__,
      py_modules=['githubnotifier'],
      install_requires=['simplejson', 'feedparser'],
      zip_safe=False,
      packages=[''],
      package_dir={'': '.'},
      package_data={'': ['octocat.png']},
      entry_points="""
        [console_scripts]
        github-notifier = githubnotifier:main
        """
)

