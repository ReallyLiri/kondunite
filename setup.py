from setuptools import setup, find_packages

setup(
    name="kondunite",
    description="Kubernetes Conditional Manifests Unifier",
    version='0.1',
    author='apiiro',
    url='https://github.com/apiiro/kondunite',
    author_email='liri@apiiro.com',
    py_modules=['kondunite'],
    install_requires=[
        'Click',
        'ruamel.yaml',
        'toposort',
    ],
    python_requires='>=3',
    packages=find_packages(),
    entry_points='''
        [console_scripts]
        kondunite=kondunite:cli
    ''',
)
