#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
patch.py

Patches the sys module to include an import hook
"""

__version__ = 0.1
__author__  = "Fin"

# Stdlib Imports
from collections import OrderedDict
import sys
import imp
import ast

# Third Party Imports
from astmonkey.transformers import ParentNodeTransformer
#from inliner.searcher import InlineMethodLocator
#from inliner.transformer import FunctionInliner

# DSP Imports


def getFunctionName(func):
    if hasattr(func, "id"):
        return func.id
    else:
        if isinstance(func, ast.Attribute):
            return func.attr
        # Might be a class item
        return func.name


def getFunctionHandler(func):
    # We take an ast.FunctionDef and return a FunctionHandler that is able to inline the function
    #if len(func.body) == 1:

        # Looks like a simple function
        #body = func.body[0]
        #if isinstance(body, (ast.Return, ast.expr)):
    return SimpleFunctionHandler()

    #return None


class InlineMethodLocator(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}

    def visit_FunctionDef(self, node):
        if any(filter(lambda d: d.id == "inline", node.decorator_list)):
            func_name = getFunctionName(node)
            self.functions[func_name] = node


class FunctionInliner(ast.NodeTransformer):
    def __init__(self, functions_to_inline):
        self.inline_funcs = functions_to_inline

    def visit_Expr(self, node):
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Assign):
            # A function call has turned into an assignment. Just return that instead
            return node.value
        return node

    def visit_Call(self, node):
        func = node.func
        func_name = getFunctionName(func)
        if func_name in self.inline_funcs:
            print func_name
            func_to_inline = self.inline_funcs[func_name]
            transformer = getFunctionHandler(func_to_inline)
            print transformer
            if transformer is not None:
                node = transformer.inline(node, func_to_inline)

        return node


class ParamReplacer(ast.NodeTransformer):
    def __init__(self, param_mapping):
        self.mapping = param_mapping

    def visit_Name(self, node):
        return self.mapping.get(node.id, node) or node


class BaseFunctionHandler(object):
    def replace_params_with_objects(self, target_node, inline_func, call_object):
        """
        target_node is some AST object, could be the return value of a function we are inlining.
        We need to inspect its parameters and create a dictionary then use ParamReplacer to replace
        all instances of those parameters with the local references to the objects being passed in
        """
        args = inline_func.args
        default_offset = len(args.args) - len(args.defaults)

        arg_mapping = OrderedDict()
        for idx, arg in enumerate(arg for arg in args.args if not arg.id == "self"):
            arg_mapping[arg.id] = None
            if idx >= default_offset:
                arg_mapping[arg.id] = args.defaults[idx - default_offset]

            if len(call_object.args) > idx:
                arg_mapping[arg.id] = call_object.args[idx]

        print arg_mapping

        print 'x', arg_mapping['x'].id
        print 'y', arg_mapping['y'].id

        for keyword in call_object.keywords:
            arg_mapping[keyword.arg] = keyword.value

        if len([arg for arg in args.args if arg.id == "self"]):
            # Ok, get the name of "self" (the instance of the class we are using)
            new_mapping = OrderedDict({"self": call_object.func.value})
            new_mapping.update(arg_mapping)
            arg_mapping = new_mapping

        print arg_mapping

        return ParamReplacer(arg_mapping).visit(target_node)


class SimpleFunctionHandler(BaseFunctionHandler):
    def inline(self, node, func_to_inline):
        # Its a simple function we have here. That means it is one statement and we can simply replace the
        # call with the inlined functions body
        body = func_to_inline.body[0]
        if isinstance(body, ast.Return):
            body = body.value

        return self.replace_params_with_objects(body, func_to_inline, node)


class ModuleLoader(object):
    def __init__(self, module):
        self.module = module

    def load_module(self, fullname):
        return self.module


class FinlineImporter(object):
    def find_module(self, fullname, path):
        file, pathname, description = imp.find_module(
            fullname.split(".")[-1], path)
        if not file:
            return
        try:
            src = file.read()
            tree = ast.parse(src)
            tree = ParentNodeTransformer().visit(tree)

            function_disoverer = InlineMethodLocator()
            function_disoverer.visit(tree)
            print "found funcs: %s" % function_disoverer.functions
            tree = FunctionInliner(function_disoverer.functions).visit(tree)

            module = sys.modules.setdefault(fullname,
                                            imp.new_module(fullname))
            module.__package__ = fullname.rpartition('.')[0]
            module.__file__ = file.name
            tree = ast.fix_missing_locations(tree)

            code = compile(tree, file.name, "exec")

            exec code in module.__dict__

            return ModuleLoader(module)
        except:
            raise
            return


def patch():
    sys.meta_path.append(FinlineImporter())
