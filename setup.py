import setuptools

with open("README.md", "r") as file:
  long_description = file.read()

setuptools.setup(
  name="gmsPython",
  version="0.0.4",
  author="Rasmus K. Skjødt Berg",
  author_email="rasmus.kehlet.berg@econ.ku.dk",
  description="Automating GAMS models and execution from Python",
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/ChampionApe/gamsPythonModels",
  packages=setuptools.find_packages(),
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
  ],
  python_requires='>=3.8',
  install_requires=["pandas", "scipy","openpyxl","pyDatabases","gams"],
)