import sys
from tool.func import *
import argparse
import inspect

# top-level parser
parser = argparse.ArgumentParser(prog='graph')
subparsers = parser.add_subparsers()

# set github user for downloading
parser_github = subparsers.add_parser('update')
#parser_github.add_argument('user', type=str, action='store')
#parser_github.add_argument('password', type=str, action='store')
parser_github.set_defaults(func=update)

# download
parser_download = subparsers.add_parser('download')
parser_download.set_defaults(func=download)

# create a list of files used
parser_list = subparsers.add_parser('list')
parser_list.add_argument('--path', type=str, action='store', nargs='?', default='./dictionaries/')
parser_list.add_argument('--dialects', type=bool, action='store', nargs='?', default=False)
parser_list.set_defaults(func=list_files)

#recommend
parser_recommend = subparsers.add_parser('recommend')
parser_recommend.add_argument('lang1', type=str, action='store')
parser_recommend.add_argument('lang2', type=str, action='store')
parser_recommend.set_defaults(func=recommend)

#preprocessing (mono + bi dictionaries)
parser_preproc = subparsers.add_parser('preprocessing')
parser_preproc.set_defaults(func=preprocessing)

# configuration file for a language pair
parser_configure = subparsers.add_parser('config')
parser_configure.add_argument('lang1', type=str, action='store')
parser_configure.add_argument('lang2', type=str, action='store')
parser_configure.set_defaults(func=get_relevant_languages)

# how many entries for this pair we can add
parser_addition = subparsers.add_parser('add')
parser_addition.add_argument('lang1', type=str, action='store')
parser_addition.add_argument('lang2', type=str, action='store')
parser_addition.add_argument('--n', type=int, action='store', nargs='?', default=10)
parser_addition.add_argument('--cutoff', type=int, action='store', nargs='?', default=4)
parser_addition.set_defaults(func=addition)

# create a loading file (edges of graph)
parser_load = subparsers.add_parser('load_file')
parser_load.add_argument('lang1', type=str, action='store')
parser_load.add_argument('lang2', type=str, action='store')
parser_load.add_argument('--n', type=int, action='store', nargs='?', default=10)
parser_load.set_defaults(func=load_file)

# evaluate on one-variant pairs w1-w2 in which both word have alternative edges
parser_eval = subparsers.add_parser('eval')
parser_eval.add_argument('lang1', type=str, action='store')
parser_eval.add_argument('lang2', type=str, action='store')
parser_eval.add_argument('--n', type=int, action='store', nargs='?', default=10)
parser_eval.add_argument('--topn', type=int, action='store', nargs='?', default=None)
parser_eval.add_argument('--n_iter', type=int, action='store', nargs='?', default=3)
parser_eval.add_argument('--cutoff', type=int, action='store', nargs='?', default=4)
parser_eval.set_defaults(func=eval_loop)

# preview result
parser_eval = subparsers.add_parser('preview')
parser_eval.add_argument('lang1', type=str, action='store')
parser_eval.add_argument('lang2', type=str, action='store')
parser_eval.add_argument('--topn', type=int, action='store', nargs='?', default=None)
parser_eval.add_argument('--cutoff', type=int, action='store', nargs='?', default=4)
parser_eval.set_defaults(func=get_translations)

# convert to dix section
parser_configure = subparsers.add_parser('convert')
parser_configure.add_argument('lang1', type=str, action='store')
parser_configure.add_argument('lang2', type=str, action='store')
parser_configure.set_defaults(func=convert_to_dix)

#merge dialects
parser_merge = subparsers.add_parser('merge')
parser_merge.add_argument('--lang1', type=str, action='store', nargs='+')
parser_merge.add_argument('--lang2', type=str, action='store', nargs='+')
parser_merge.set_defaults(func=merge)

#example
parser_example = subparsers.add_parser('example')
parser_example.add_argument('lang1', type=str, action='store')
parser_example.add_argument('lang2', type=str, action='store')
parser_example.add_argument('--n', type=int, action='store', nargs='?', default=10)
parser_example.add_argument('--cutoff', type=int, action='store', nargs='?', default=4)
parser_example.add_argument('--topn', type=int, action='store', nargs='?', default=None)
parser_example.add_argument('--input', type=str, action='store', nargs='?', default='')
parser_example.add_argument('--lang', type=str, action='store', nargs='?', default='')
parser_example.add_argument('--config', action='store_true', default=False)
parser_example.add_argument('--load', action='store_true', default=False)
parser_example.add_argument('--output', action='store', type=str, default='')
parser_example.set_defaults(func=example)

#grid
parser_grid = subparsers.add_parser('grid')
parser_grid.add_argument('lang1', type=str, action='store')
parser_grid.add_argument('lang2', type=str, action='store')
parser_grid.add_argument('--n', type=int, action='store', nargs='*', default=[10])
parser_grid.add_argument('--topn', type=int, action='store', nargs='*', default=[None])
parser_grid.add_argument('--cutoff', type=int, action='store', nargs='*', default=[4])
parser_grid.set_defaults(func=grid)

args = parser.parse_args()
arg_spec = inspect.getargspec(args.func)
if arg_spec.keywords:
    args_for_func = vars(args)
else:
    args_for_func = {k:getattr(args, k) for k in arg_spec.args}

args.func(**args_for_func)
