#!/usr/bin/env python3

import os, re, tempfile, subprocess, argparse

datePattern = re.compile('.*(20\d{2})-?(\d{2})-?\d{2}.*')

def run(*args):
   pcs = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
   if pcs.returncode != 0:
      for line in pcs.stdout.splitlines():
         print(line)
      return False
   else:
      for line in pcs.stdout.splitlines():
         if all(line.find(x) == -1 for x in ('cannot listen to port', 'Address already in use', 'Could not request local forwarding')):
            print(line)
      return True

def mkdir(path, host=None):
   if host:
      return run('ssh', host, f'mkdir -p {path}')
   else:
      return run('mkdir', '-p', f'{path}')
   
def rsync(inputPath, fileList, outputPath, host=None):
   args = ["rsync", "-avzz", "--files-from", fileList, inputPath]
   if host:
      args.append(f'{host}:{outputPath}')
   else:
      args.append(f'{outputPath}')

   return run(*args)

def sortFiles(inputPath):
   files = {}
   orphans = []

   for directory, dirnames, filenames in os.walk(inputPath):
      for filename in filenames:
         m = datePattern.match(filename)
         if m:
            year = m.group(1)
            month = m.group(2)
            files.setdefault(directory, {}).setdefault(year, {}).setdefault(month, []).append(filename + '\n')
         else:
            orphans.append(os.path.join(os.path.relpath(directory, inputPath), filename + '\n'))
   return (files, orphans)

def createYearDirs(files, outputPath, host=None):
   years = set()
   for directory in files:
      for year in files[directory]:
         years.add(year)
   
   for year in years:
      yearOut = f'{outputPath}/{year}'
      if not mkdir(yearOut, host):
         print(f'Cannot create directory: {yearOut}')
         return False
   
   return True

def backup(inputPath, outputPath, host=None):
   (files, orphans) = sortFiles(inputPath)

   if not createYearDirs(files, outputPath, host):
      return False
   
   filesList = tempfile.NamedTemporaryFile('w', delete=True)
   for directory in files:
      for year in files[directory]:
         for month in files[directory][year]:
            with open(filesList.name, 'w') as f:
               f.writelines(files[directory][year][month])

            monthOut = f'{outputPath}/{year}/{month}/'
            if not rsync(directory, filesList.name, monthOut, host):
               print(f'Cannot rsync directory {directory} to {monthOut}')
               return False
            else:
               print(f'ok: {monthOut}')
   
   if orphans:
      with open(filesList.name, 'w') as f:
         f.writelines(orphans)

      if not rsync(inputPath, filesList.name, outputPath, host):
         print(f'Cannot rsync orphans from directory {inputPath} to {outputPath}')
         return False
      else:
         print(f'ok orphans: {outputPath}')
   
   return True

if __name__ == "__main__":
   parser = argparse.ArgumentParser(description='Backup by year and month')
   parser.add_argument('input')
   parser.add_argument('--host', help='Output host')
   parser.add_argument('output')
   args = parser.parse_args()

   inputPath = os.path.realpath(os.path.expanduser(args.input))
   print(f'Input folder: {inputPath}')

   outputPath = os.path.realpath(os.path.expanduser(args.output))
   print(f'Output folder: {outputPath}')

   if args.host:
      print(f'Host: {args.host}')
   
   if backup(inputPath, outputPath, args.host):
      print('Backup completed successfully')
   else:
      print('Some error has occured')
