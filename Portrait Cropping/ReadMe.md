## AK Portrait Cropping


### Version
- v0.7b | 19.02.2023
- by VaDiM#5824


### Description
- Tool for cropping portraits from portrait atlases


### Folder structure
- `MonoBehaviour`: Folder with exported MonoBehaviour files (.json)
- `Texture2D`: Folder with exported atlas images (.png)
- `_output`: Auto generated folder with processed portraits
- `AkPortraitCropping.py`: Script itself (for AssetStudio)
- `AkPortraitCropping_UnityPy.py`: Script itself (UnityPy ver)


### Requirements
- Python 3.8+
- `Pillow` library (`python -m pip install --upgrade Pillow`)
- `UnityPy` library (`python -m pip install --upgrade UnityPy`) (required only for UnityPy ver of script)
- Or use `pip install -r requirements.txt` / `pipenv install`


### Usage

#### AkPortraitCropping.py:
1. Run AssetStudio and load `charportraits` folder with all .ab files there.
2. Click `Export` -> `All assets` and export assets to the script folder.
   Note, that the `Texture2D` and `MonoBehaviour` folders **must be empty** if you want to export assets from AssetStudio directly to the script folder.
   Or move exported atlases and jsons to the corresponding folders, if you exported them to another location.
3. Run the script and wait for the result.
    ```bash
    python AkPortraitCropping.py [image_format]
    ```
    - `image_format`: Format of the output portrait images. Supported values: `-png`, `-webp`.
4. Enjoy!

#### AkPortraitCropping_UnityPy.py:
1. Run the script and wait for the result.
    ```bash
    python AkPortraitCropping_UnityPy.py [input_path] [image_format]
    ```
    - `input_path`: A path to the game\`s .apk file *(for cn or bilibili server)* or to the `charportraits` folder containing portrait asset files (portrait_hub.ab, pack[x].ab).
    - `image_format`: Format of the output portrait images. Supported values: `-png`, `-webp`.
2. Enjoy!


### Special thanks
- [K0lb3](https://github.com/K0lb3) ([UnityPy](https://github.com/K0lb3/UnityPy))
- [Perfare](https://github.com/Perfare) ([AssetStudio](https://github.com/Perfare/AssetStudio))


### Version history
**v0.7b | 19.02.2023**
- added UnityPy version of the script (AkPortraitCropping_UnityPy.py)
- added requirements.txt and Pipfile for pipenv
- converted image_format to Enum
- updated ReadMe
- minor code fixes

**v0.6b | 22.11.2022**
- added option to save portraits in webp lossy format

**v0.5b | 29.09.2022**
- made a small refactoring: changed threads to multiprocessing

**v0.4b | 30.01.2022**
- fixed a potential bug due to duplicated sprites in json files
- optimized performance by using threads

**v0.3b | 18.01.2022**
- fixed unix compatibility

**v0.2b | 07.12.2021**
- added support for partial processing of a `portrait_hub` file

**v0.1b | 05.11.2021**
- initial version


### Testing
- Tested on `mrfz_1.9.62_20230114_051821_3aa6b.apk`
- Tested on `arknights-hg-1962.apk`
