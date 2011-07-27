#!/usr/bin/python3
import os
import os.path
import shutil
import sys
from subprocess import Popen, PIPE
from argparse import ArgumentParser
import utils
from myconfig import MyConfig


#Please `make -f Makefile.data prepare` first

config = MyConfig()

#change cwd to the libpinyin evals tool directory
libpinyindir = config.getEvalsDir()
os.chdir(libpinyindir)

datafiles = ['gb_char.table',  'gbk_char.table', \
                 config.getFinalModelFileName(), 'evals.text', \
                 'deleted_bigram.db']


def checkData():
    cwd = os.getcwd()
    os.chdir(os.path.join(libpinyindir, 'data'))
    for onefile in datafiles:
        if not os.access(onefile, os.F_OK):
            sys.exit('missing one data file:' + onefile)
    os.chdir(cwd)


def cleanUpData():
    #begin processing
    cmdline = ['/usr/bin/make', '-f', 'Makefile.data', 'clean']
    subprocess = Popen(cmdline, shell=False, close_fds=True)
    (pid, status) = os.waitpid(subprocess.pid, 0)
    if status != 0:
        sys.exit('make clean for data files failed.')
    #end processing


def buildData():
    #begin processing
    cmdline = ['/usr/bin/make', '-f', 'Makefile.data', 'build']
    subprocess = Popen(cmdline, shell=False, close_fds=True)
    (pid, status) = os.waitpid(subprocess.pid, 0)
    if status != 0:
        sys.exit('make build for data files failed.')
    #end processing


def estimateModel():
    #change to utils/training subdir
    cwd = os.getcwd()
    os.chdir(os.path.join(libpinyindir, 'utils', 'training'))

    result_line_prefix = "average lambda:"
    avg_lambda = 0.

    #begin processing
    cmdline = ['./estimate_interpolation']

    subprocess = Popen(cmdline, shell=False, stdout=PIPE, \
                           close_fds=True)

    for line in subprocess.stdout.readlines():
        #remove trailing '\n'
        line = line.rstrip(os.linesep)
        if line.startswith(result_line_prefix):
            avg_lambda = float(line[len(result_line_prefix):])

    os.waitpid(subprocess.pid, 0)
    #end processing

    os.chdir(cwd)
    return avg_lambda


def modifyCodeforLambda(lambdaparam):
    #begin processing
    cmdline = ['/usr/bin/make', '-f', 'Makefile.data', 'rebuild', \
                   'LAMBDA_PARAMETER=' + lambdaparam]
    subprocess = Popen(cmdline, shell=False, close_fds=True)
    (pid, status) = os.waitpid(subprocess.pid, 0)
    if status != 0:
        sys.exit('make rebuild for data files failed.')
    #end processing


def evaluateModel():
    #change to utils/training subdir
    cwd = os.getcwd()
    os.chdir(os.path.join(libpinyindir, 'utils', 'training'))

    result_line_prefix = "correction rate:"
    rate = 0.

    #begin processing
    cmdline = ['./eval_correction_rate']

    subprocess = Popen(cmdline, shell=False, stdout=PIPE, \
                           close_fds=True)

    for line in subprocess.stdout.readlines():
        #remove training '\n'
        line = line.rstrip(os.linesep)
        if line.startswith(result_line_prefix):
            rate = float(line[len(result_line_prefix):])

    os.waitpid(subprocess.pid, 0)
    #end processing

    os.chdir(cwd)
    return rate

if __name__ == '__main__':
    parser = ArgumentParser(description='Evaluate correction rate.')
    parser.add_argument('--finaldir', action='store', \
                            help='final directory', \
                            default=config.getFinalModelDir())
    parser.add_argument('tryname', action='store', \
                            help='the storage directory')

    args = parser.parse_args()
    print(args)
    tryname = 'try' + args.tryname

    trydir = os.path.join(args.finaldir, tryname)
    if not os.access(trydir, os.F_OK):
        sys.exit(tryname + "doesn't exist.")

    cwdstatuspath = os.path.join(trydir, config.getFinalStatusFileName())
    cwdstatus = utils.load_status(cwdstatuspath)
    if not utils.check_epoch(cwdstatus, 'Prune'):
        raise utils.EpochError('Please tryprune first.')

    if utils.check_epoch(cwdstatus, 'Evaluate'):
        sys.exit('already evaluated.')

    print('checking')
    checkData()

    modelfile = os.path.join(trydir, config.getFinalModelFileName())
    destfile = os.path.join(libpinyindir, 'data', \
                                config.getFinalModelFileName())
    print('copying from ' + modelfile + ' to ' + destfile)
    shutil.copyfile(modelfile, destfile)

    print('cleaning')
    cleanUpData()
    print('building')
    buildData()
    print('estimating')
    avg_lambda = estimateModel()

    cwdstatus['EvaluateAverageLambda'] = avg_lambda
    utils.store_status(cwdstatuspath, cwdstatus)

    print('rebuilding')
    modifyCodeforLambda(avg_lambda)
    print('evaluating')
    rate = evaluateModel()
    print(tryname + "'s correction rate:" + rate)

    cwdstatus['EvaluateCorrectionRate'] = rate
    utils.store_status(cwdstatuspath, cwdstatus)

    utils.sign_epoch(cwdstatus, 'Evaluate')
    utils.store_status(cwdstatuspath, cwdstatus)
    print('done')
