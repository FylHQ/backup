#!/usr/bin/env python3

import os, re, tempfile, subprocess, argparse

datePattern = re.compile('.*(20\d{2})-?(\d{2})-?\d{2}.*')

def run(*args):
   pcs = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
   for line in pcs.stdout.splitlines():
      if all(line.find(x) == -1 for x in ('cannot listen to port', 'Address already in use', 'Could not request local forwarding')):
         print(line)
   if pcs.returncode != 0:
      return False
   else:
      return True

def mkdir(path, host=None):
   if host:
      return run('ssh', host, f'mkdir -p "{path}"')
   else:
      return run('mkdir', '-p', f'{path}')
   
def rsync(inputPath, fileList, outputPath, dryRun=False, host=None):
   args = ["rsync", "-avzz", "--files-from", fileList, inputPath]
   if dryRun:
      args.append('-n')
   
   if host:
      args.append(f'{host}:"{outputPath}"')
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

def backup(inputPath, outputPath, dryRun=False, host=None):
   (files, orphans) = sortFiles(inputPath)

   if not dryRun and not createYearDirs(files, outputPath, host):
      return False
   
   filesList = tempfile.NamedTemporaryFile('w', delete=True)
   for directory in files:
      for year in files[directory]:
         for month in files[directory][year]:
            with open(filesList.name, 'w') as f:
               f.writelines(files[directory][year][month])

            monthOut = f'{outputPath}/{year}/{month}/'
            if not rsync(directory, filesList.name, monthOut, dryRun, host):
               print(f'Cannot rsync directory {directory} to {monthOut}')
               return False
            else:
               print(f'ok: {monthOut}')
   
   if orphans:
      with open(filesList.name, 'w') as f:
         f.writelines(orphans)

      if not rsync(inputPath, filesList.name, outputPath, dryRun, host):
         print(f'Cannot rsync orphans from directory {inputPath} to {outputPath}')
         return False
      else:
         print(f'ok orphans: {outputPath}')
   
   return True

if __name__ == "__main__":
   parser = argparse.ArgumentParser(description='Backup by year and month', add_help=False)
   parser.add_argument('--help', action='help', default=argparse.SUPPRESS, help=argparse._('show this help message and exit'))
   parser.add_argument('input')
   parser.add_argument('--host', '-h', help='Output host')
   parser.add_argument('--dry-run', '-n', action="store_true", help='Perform a trial run with no changes made')
   parser.add_argument('output')
   args = parser.parse_args()

   print(args)

   inputPath = os.path.realpath(os.path.expanduser(args.input))
   print(f'Input folder: {inputPath}')

   outputPath = os.path.realpath(os.path.expanduser(args.output))
   print(f'Output folder: {outputPath}')

   if args.dry_run:
      print('Performing dry run')

   if args.host:
      print(f'Host: {args.host}')
   
   if backup(inputPath, outputPath, args.dry_run, args.host):
      print('Backup completed successfully')
   else:
      print('Some error has occured')
