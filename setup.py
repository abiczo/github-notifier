from setuptools import setup

setup(name='github-notifier',
      description='Github updates notifier for Linux',
      author='Andras Biczo',
      author_email='abiczo@gmail.com',
      url='http://github.com/abiczo/github-notifier',
      license='MIT',
      version='0.1',
      py_modules=['githubnotifier'],
      install_requires=['simplejson', 'feedparser'],
      zip_safe=False,
      entry_points="""
        [console_scripts]
        github-notifier = githubnotifier:main
        """
)

