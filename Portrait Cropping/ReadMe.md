## AK Portrait Cropping


### Version
- v0.6b | 22.11.2022
- by VaDiM#5824


### Description
- Tool for cropping portraits from portrait atlases


### Folder structure
- `MonoBehaviour`: Folder with exported MonoBehaviour files (.json)
- `Texture2D`: Folder with exported atlas images (.png)
- `_output`: Auto generated folder with processed portraits
- `AkPortraitCropping.py`: Script itself

	
### Requirements
- Python 3.8+
- Pillow library (`python -m pip install --upgrade Pillow`)

	
### Usage
1. Run AssetStudio and load `charportraits` folder with all .ab files there.
2. Click `Export` -> `All assets` and export assets to the script folder. 
Note, that the `Texture2D` and `MonoBehaviour` folders **must be empty** if you want to export assets from AssetStudio directly to the script folder.
Or move exported atlases and jsons to the corresponding folders, if you exported them to another location.
3. Run `AkPortraitCropping.py` and wait for the result. 
You can also specify format of the output portrait images by running the script with args: `AkPortraitCropping.py -png` for png and `AkPortraitCropping.py -webp` for webp.
4. Enjoy!


### Version history
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
- Tested on `mrfz_1.9.21_20221027_060143_3e57c.apk`
