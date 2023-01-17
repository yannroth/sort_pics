#!/usr/bin/python3
 
import os
import argparse
import datetime
from PIL import Image, ExifTags
import re
import subprocess
import time
import logging

version = '1.1.0'
date_format = '%Y-%m-%d'
jpeg_ext = ['.jpg', '.JPG', '.jpeg', '.JPEG']
png_ext = ['.png', '.PNG']
extensions = jpeg_ext + png_ext

skip_dates = []
auto_dates = []

def existing_dir(string):
    if not os.path.exists(string):
        raise argparse.ArgumentTypeError(repr(string) + " does not exist.")
    if not os.path.isdir(string):
        raise argparse.ArgumentTypeError(repr(string) + " is not a directory.")
    return string

def input_date(string):
    date = datetime.datetime.strptime(string, date_format)
    return date

def get_creation_date(file):
    exif_date_format = '%Y:%m:%d'
    exif_regex_format = '[0-9]{4}\:[0-9]{2}\:[0-9]{2}'
    filename_regex_format = '[0-9]{8}'
    filename_date_format = '%Y%m%d'

    with Image.open(file) as img:
        exif = { ExifTags.TAGS[k]: v for k, v in img._getexif().items() if k in ExifTags.TAGS }

    try:
        date_str = exif['DateTimeOriginal']
        date_str = re.search(exif_regex_format, date_str).group(0)
        date = datetime.datetime.strptime(date_str, exif_date_format)
    except (ValueError, KeyError, IndexError):
        pass
    else:
        return date

    try:
        date_str = exif['DateTime']
        date_str = re.search(exif_regex_format, date_str).group(0)
        date = datetime.datetime.strptime(date_str, exif_date_format)
    except (ValueError, KeyError, IndexError):
        pass
    else:
        return date

    try:
        print('trying with filename')
        filename = os.path.basename(file)
        date_str = re.search(filename_regex_format, filename).group(0)
        date = datetime.datetime.strptime(date_str, filename_date_format)
    except (ValueError, IndexError, AttributeError):
        pass
    else:
        return date
    
    raise ValueError(file + ': Could not find file date')

def get_folder_date(folder):
    folder_regex_format = '[0-9]{4}\-[0-9]{2}\-[0-9]{2}'

    try:
        basename = os.path.basename(folder)
        date_str = re.search(folder_regex_format, basename).group(0)
        date = datetime.datetime.strptime(date_str, date_format)
    except (ValueError, IndexError, AttributeError):
        raise ValueError('Could not find date in folder name')

    return date

def get_output_folder(root, date):
    subfolders = [ f.path for f in os.scandir(root) if f.is_dir() ]

    for folder in subfolders:
        folder_date = get_folder_date(folder)
        if date == folder_date:
            return folder
    
    return None

def move(src, dst):
    out_dir = os.path.dirname(dst)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        logging.info(out_dir + ' created')

    if not os.path.isdir(out_dir):
        raise ValueError(out_dir + ' exists but is not a directory')

    os.rename(src, dst)
    logging.info(src + ' --> ' + dst)

def move_prompt(file: str, folder: str, sub_dir: str, date: datetime.datetime):
    response = input('Do you want to move "' + file + '" into "' + folder + '" [y,n,a,s,q,?] ? ')
    if response == 'a':
        auto_dates.append(date)

    if response == 'y' or response == 'a':
        out_file = os.path.join(folder, sub_dir, os.path.basename(file))
        move(file, out_file)

    elif response == 'n':
        logging.info(file + ' skipped')
        pass

    elif response == 's':
        skip_dates.append(date)

    elif response == 'q':
        raise StopIteration

    else:
        print('y - Move file')
        print('n - Do not move file')
        print('a - Move all with this date')
        print('s - Skip all with this date')
        print('q - Quit and cancel later files')
        print('? - Print help')
        move_prompt(file, folder, sub_dir, date)

def create_prompt(file: str, date: datetime.datetime, lib: str):
    folder = ''
    date_str = date.strftime(date_format)
    response = input('Do you want to create a folder for ' + date_str + ' [y,n,s,q,?] ? ')
    if response == 'y':
        input_name = input('Enter folder name (date will be prefixed automatically): ')
        folder_name = date_str + ' ' + input_name.lstrip().rstrip()
        folder = os.path.join(lib, folder_name)

    elif response == 'n':
        logging.info(file + ' skipped')
        pass

    elif response == 's':
        logging.info(file + ' skipped')
        skip_dates.append(date)

    elif response == 'q':
        raise StopIteration

    else:
        print('y - Move file')
        print('n - Do not move file')
        print('s - Skip all with this date')
        print('q - Quit and cancel later files')
        print('? - Print help')
        folder = create_prompt(file, date, lib)

    return folder

def auto_response(skip: list, auto: list, file: str, folder: str, sub_dir: str, date: datetime.datetime):
    if date in skip:
        logging.info(file + ' skipped')
        return True

    if date in auto:
        out_file = os.path.join(folder, sub_dir, os.path.basename(file))
        move(file, out_file)
        return True

    return False

def create_and_move_prompt(file: str, folder: str, date: datetime.datetime, lib: str, sub_dir: str, viewer_sw: str):

    if auto_response(skip_dates, auto_dates, file, folder, sub_dir, date):
        return

    try:
        viewer = display_pic(file, viewer_sw)
        if not folder:
            folder = create_prompt(file, date, lib)

        if folder:
            move_prompt(file, folder, sub_dir, date)
    finally:
        close_pic(viewer)

    return

def get_files_recursive(folder, filters=[]):
    list_files = []
    for root, _, files in os.walk(folder):
        for filename in files:
            file = os.path.join(root, filename)
            _, extension = os.path.splitext(file)
            if extension in filters:
                list_files.append(file)

    list_files.sort()
    return list_files

def display_pic(filename: str, viewer_sw: str):
    fh = open('NUL', 'w')
    viewer = subprocess.Popen([viewer_sw, filename], stdout=fh, stderr=fh)
    fh.close()
    time.sleep(0.3)
    subprocess.call(['xdotool', 'click', '1'])
    return viewer

def close_pic(viewer):
    viewer.terminate()
    viewer.kill()

def cli_args():
    parser = argparse.ArgumentParser(description='Helps sort pictures into an existing tree using date prefixed folders')
    parser.add_argument('input', type=existing_dir, help='Input directory containing pictures to sort')
    parser.add_argument('library', type=existing_dir, help='Output directory containing (or not) an existing picture library')
    parser.add_argument('-s', '--start', type=input_date, default='1970-01-01', help='Pictures taken before this start date are ignored, ex: "2021-01-31"')
    parser.add_argument('-p', '--stop', type=input_date, default=datetime.datetime.now().strftime(date_format), help='Pictures taken after this stop date are ignored, ex: "2022-12-31"')
    parser.add_argument('-sd', '--sub_dir', type=str, default='', help='Create a sub-dir with the provided name into libraries folders')
    parser.add_argument('-sw', '--viewer_sw', type=str, default='nomacs', help='Switch the software used to view open the pictures')
    parser.add_argument('-l', '--log', type=str, default=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.log', help='Provide log file name')
    parser.add_argument('-v', '--version', action='store_true', default=False, help='Print version and quit')
    return parser.parse_args()

def main():
    args = cli_args()

    if args.version:
        print(version)
        return

    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        handlers=[
            logging.FileHandler(args.log),
            logging.StreamHandler()
        ]
    )

    input_files = get_files_recursive(args.input, extensions)
    for file in input_files:
        file_date = get_creation_date(file)
        if file_date < args.start or file_date > args.stop:
            continue

        output_folder = get_output_folder(args.library, file_date)
        try:
            create_and_move_prompt(file, output_folder, file_date, args.library, args.sub_dir, args.viewer_sw)
        except StopIteration:
            logging.info('Stopped by user')
            return
        except NotImplementedError:
            pass

    logging.info('All files treated')

if __name__ == '__main__':
    main()
