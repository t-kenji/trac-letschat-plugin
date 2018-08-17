from setuptools import setup

setup(
    name='LetschatNotificationPlugin',
    version='0.9.2',
    description='Plugin to announce Trac changes in Lets Chat',
    author='Takahashi Kenji',
    url='https://github.com/t-kenji/trac-letschat-plugin',
    license='BSD',
    packages=['letschat_notification'],
    classifiers=[
        'Framework :: Trac',
        'License :: OSI Approved :: BSD License',
    ],
    install_requires=[
        'Trac',
    ],
    entry_points={
        'trac.plugins': [
            'letschat_notification = letschat_notification'
        ]
    }
)
