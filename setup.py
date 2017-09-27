from distutils.core import setup

setup(
    name='soccerprediction',
    version='0.0.2',
    py_modules=['soccerprediction'],
    url='https://github.com/steviecurrie/soccer-prediction',
    license='Do what thou wilt',
    author='Steven Currie',
    author_email='scayrsteven@gmail.com',
    description='Soccer prediction using poisson distribution',
    requires=['pandas', 'numpy', 'requests', 'beautifulsoup4']
)
