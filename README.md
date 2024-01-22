# MediaVideoTools

Various tools for (video) media information (e.g., MKV), automatic batch conversion to
x265/HEVC, video language checks, checks for filenames, automatic renaming, etc.

| Tool                         | Description                                      |
|------------------------------|--------------------------------------------------|
| media_stats.py               | Collect statistics on media files.               |
| mime_checker.py              | MIME type of files, e.g., check if video.        |
| mkv_metadata.py              | Various MKV metadata utility methods.            |
| rename_based_on_dirname.py   | MKV renaming based on the parent's folder name.  |
| rename_x265_remove_x264.py   | Fix x265 MKV files with abundant "x264".         |
| video_canonavi_rename.py     | Canon AVI files renaming with date & time.       |
| video_convert_x265.py        | Video to x265/HEVC conversion.                   |
| video_find_big.py            | Find big video files, CSV output.                |
| video_find_not_searchable.py | Find video files which are not searchable.       |
| video_info.py                | Extract video metadata information (CSV output). |
| video_language_check.py      | Check if filename contains correct [LANG] tag.   |

## Requirements

- Python 3.9+
- Poetry (see https://python-poetry.org/docs/#installation)
- On MS Windows: extra manual installation of libmagic is necessary.
    1. `poetry add python-magic-bin`
    2. Download and place https://github.com/nscaife/file-windows/releases/tag/20170108 into `.`
       (c.f. https://github.com/julian-r/python-magic#dependencies)

## How-To Use

1. Preparations (see above):
    1. install poetry: https://python-poetry.org/docs/#installation
    2. on MS Windows, install libmagic binaries (see above)
2. `poetry install --only=main`
3. `poetry run python mediavideotools/<tool.py> --help`

## Video Filename Language Check (video_language_check)

Python script which finds all video files and checks if the containing folder
name has the correct language tags according to the video file's audio tracks.

Say you have a (huge) collection of video files (movies), and you include language
tags such as '[EN]' in the folder names to depict the audio language in the video file.

However, checking for the correct language tags could be tedious for a large
number of folders and files.

Example:
A video file with English and German as audio tracks.

Wrong folder name (`[DE]` is missing):

```
My Great Movie (2020) [EN]
```

Correct folder name:

```
My Great Movie (2020) [EN][DE]
```


## rename_based_on_dirname

Sometimes MKV video files are just named "funxd.mkv", without any semantics.
However, the semantic could be in the file's folder name.
The idea is to rename the MKV file based on the folder name.

Example:

`Der Stiefelkater (2011) [DE]/poe-dgk_cut.avi`

-->

`Der Stiefelkater (2011) [DE]/Der Stiefelkater (2011) [DE].avi`


## Video x265 Converter (video_convert_x265)

Converts video files using ffmpeg to x265/HEVC.
Recursively scan for all video files for automatic processing.
Processed files are renamed to indicate their processed-status.
Annotate resulting MKV files with metadata (using mkvpropedit).

Sometimes you want to convert a lot of video files automatically.
This Python program does that.



## Video Info to CSV (video_info)

Extracts important video information (codec, duration, bit_rate, etc.)
and writes it to a CSV file.
Fields of interest are a.o. "format", "codecs_video",
"video_format_list", "video_language_list", "duration",
"audio_codecs", etc. (see Python file)

Example:
```
filename;file_size;format;duration;video_codecs;audio_codecs;audio_language_list;text_language_list;format;format_profile;encoded_library_name;bit_rate;bit_rate_mode;pixel_aspect_ratio;proportion_of_this_stream
"testdata/correct/Cool Run (1993) [EN]/subdir/cool.run.1993.720p.bluray.hevc.x265.rmteam_cut.mkv";21960;Matroska;1020;;AAC LC;English;English;HEVC;Main@L3.1@Main;x265;6455885;;1.000;
...
```

## Media Stats (media_stats)

Recursively collects statistics (e.g., duration) on video and
audio media files. The output is CSV.

Example:
```
path;level;num_entries;cum_filesize_bytes;cum_duration_seconds;mean_bit_rate
"testdata/correct/Cool Run (1993) [EN]/subdir";4;1;21960;1.02;172235.0
"testdata/correct/Cool Run (1993) [EN]";3;1;21960;1.02;172235.0
"testdata/correct";2;10;1736671;12.576;1207007.1
"testdata";1;2;2190850;114.903;871183.0
```
