#!/usr/bin/env python3

import os, sys, re, tempfile, subprocess, argparse

datePattern = re.compile('.*(20\d{2})-?(\d{2})-?\d{2}.*')


def run(*args):
   """p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
   for line in p.stdout.splitlines():
      if all(line.find(x) == -1 for x in ('cannot listen to port', 'Address already in use', 'Could not request local forwarding')):
         print(line)"""

   p = subprocess.run(args, stdout=sys.stdout, stderr=sys.stderr)
   if p.returncode != 0:
      return False
   else:
      return True

def mkdir(host, path):
   if host:
      return run('ssh', host, f'mkdir -p "{path}"')
   else:
      return run('mkdir', '-p', f'{path}')
   
def rsync(inputPath, host, outputPath, fileList, showProgress, dryRun):
   args = ["rsync", "-av", "--chmod=Du=rwx,Dg=rwx,Do=rx,Fu=rw,Fg=rw,Fo=r"]
   if fileList:
      args.append('--files-from')
      args.append(fileList)

   if dryRun:
      args.append('-n')

   if showProgress:
      args.append('--progress')

   args.append(inputPath)
   
   if host:
      args.append(f'{host}:"{outputPath}"')
   else:
      args.append(f'{outputPath}')

   return run(*args)

def sortFiles(inputPath, startMonth):
   files = {}
   orphans = []

   for directory, dirnames, filenames in os.walk(inputPath):
      for filename in filenames:
         m = datePattern.match(filename)
         if m:
            year = m.group(1)
            month = m.group(2)
            
            if not startMonth or (int(year) * 100 + int(month) >= startMonth):
               files.setdefault(directory, {}).setdefault(year, {}).setdefault(month, []).append(filename + '\n')
         else:
            orphans.append(os.path.join(os.path.relpath(directory, inputPath), filename + '\n'))
   return (files, orphans)

def createYearDirs(files, host, outputPath):
   years = set()
   for directory in files:
      for year in files[directory]:
         years.add(year)
   
   for year in years:
      yearOut = f'{outputPath}/{year}'
      if not mkdir(host, yearOut):
         print(f'Cannot create directory: {yearOut}')
         return False
   
   return True

def backup(inputPath, startMonth, host, outputPath, showProgress, dryRun):
   (files, orphans) = sortFiles(inputPath, startMonth)

   if not dryRun and not createYearDirs(files, host, outputPath):
      return False
   
   filesList = tempfile.NamedTemporaryFile('w', delete=True)
   for directory in files:
      for year in files[directory]:
         for month in files[directory][year]:
            with open(filesList.name, 'w') as f:
               f.writelines(files[directory][year][month])

            monthOut = f'{outputPath}/{year}/{month}/'
            if not rsync(directory, host, monthOut, filesList.name, showProgress, dryRun):
               print(f'Cannot rsync directory {directory} to {monthOut}')
               return False
            else:
               print(f'ok: {monthOut}')
   
   if orphans:
      with open(filesList.name, 'w') as f:
         f.writelines(orphans)

      if not rsync(inputPath, host, outputPath, filesList.name, showProgress, dryRun):
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
   parser.add_argument('--start', '-s', type=int, help='Start month (YYYYMM)')
   parser.add_argument('--dry-run', '-n', action="store_true", help='Perform a trial run with no changes made')
   parser.add_argument('--progress', action="store_true", help='Show progress during transfer')
   parser.add_argument('--raw', action="store_true", help='Backup without breakdown into years and months')
   parser.add_argument('output')
   args = parser.parse_args()

   inputPath = os.path.realpath(os.path.expanduser(args.input))
   if args.raw and args.input.endswith('/'):
      inputPath += '/'
   print(f'Input folder: {inputPath}')

   outputPath = os.path.realpath(os.path.expanduser(args.output))
   print(f'Output folder: {outputPath}')

   if args.start:
      print(f'Start month: {args.start}')

   if args.dry_run:
      print('Performing dry run')

   if args.host:
      print(f'Host: {args.host}')
   
   if args.raw:
      result = rsync(inputPath, args.host, outputPath, None, args.progress, args.dry_run)
   else:
      result = backup(inputPath, args.start, args.host, outputPath, args.progress, args.dry_run)

   if result:
      print('Backup completed successfully')
   else:
      print('Some error has occured')
