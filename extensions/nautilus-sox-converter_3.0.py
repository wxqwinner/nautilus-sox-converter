"""
nautilus-sox-converter.py Sox converter for nautilus.

@history
 2022-05-23 wxqwinner Created.

Copyright (c) 2022~ wxqwinner.
"""

import re
import os
import subprocess
import multiprocessing as mp
from urllib.parse import unquote
from gi.repository import Nautilus, GObject, Gio, Gtk, GLib, GdkPixbuf

AUDIO_CONVERTER_CMD = 'sox'

ACCEPTED_EXTENSIONS = set(('raw', 'pcm', 'wav'))

SOX_CONVERTER_LIST = [
    {'label':'r8000c1i16', 'suffix':'_r8000_c1_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 8000 -c 1 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r8000c2i16', 'suffix':'_r8000_c2_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 8000 -c 2 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r16000c1i16', 'suffix':'_r16000_c1_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 16000 -c 1 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r16000c2i16', 'suffix':'_r16000_c2_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 16000 -c 2 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r44100c1i16', 'suffix':'_r44100_c1_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 44100 -c 1 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r44100c2i16', 'suffix':'_r44100_c2_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 44100 -c 2 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r48000c1i16', 'suffix':'_r48000_c1_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 48000 -c 1 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'r48000c2i16', 'suffix':'_r48000_c2_i16', 'param':{'gopts':'', 'ifopts':'', 'ofopts':'-r 48000 -c 2 -e signed-integer -b 16'}, 'ext_type':('wav', 'pcm', 'raw')},
    {'label':'raw', 'suffix':'', 'param':{'gopts':'--magic', 'ifopts':'', 'ofopts':'-t raw'}, 'ext_type':['wav']}
]


def get_file_ext(file):
    filename = unquote(file.get_uri()[7:])
    parts = filename.split('.')
    if len(parts) < 2:
        return None
    ext = str.lower(parts[-1])
    return ext


def find_uri_not_in_use(new_uri):
    i = 1
    while os.path.isfile(new_uri):
        new_uri = new_uri.split('.')
        new_uri[-2] = new_uri[-2] + '_' + str(i)
        new_uri = '.'.join(new_uri)
        i = i + 1
    return new_uri


def change_uri(old_path, suffix, new_extension):
    if suffix:
        old_path = re.sub(r'[_][r][0-9]{4,5}[_][c][0-9][_][i,u][0-9]{1,2}', "", old_path) # "_r8000_c1_i16" [_r]^\d{4,5}[_c]^\d{1}^[a-z]{1}^\d{1,2}
    split_ver = old_path.split('.')
    split_ver[-2] = f'{split_ver[-2]}{suffix}'
    split_ver[-1] = new_extension
    return '.'.join(split_ver)


class SoxConverterMenu(GObject.GObject, Nautilus.MenuProvider, Nautilus.LocationWidgetProvider):
    def __init__(self):
        super().__init__()
        self.infobar_hbox = None
        self.infobar = None
        self.process = None
        self.other_processes = mp.Queue()

    def get_widget(self, uri, window) -> Gtk.Widget:
        """ This is the method that we have to implement (because we're
        a LocationWidgetProvider) in order to show our infobar.
        """
        self.infobar = Gtk.InfoBar()
        self.infobar.set_message_type(Gtk.MessageType.ERROR)
        self.infobar.connect("response", self.__cb_infobar_response)

        return self.infobar

    def __cb_infobar_response(self, infobar, response):
        """ Callback for the infobar close button.
        """
        if response == Gtk.ResponseType.CLOSE:
            self.infobar_hbox.destroy()
            self.infobar.hide()
            if self.process is not None and self.process.is_alive():
                self.process.terminate()
                self.process.join()
            while not self.other_processes.empty():
                try:
                    os.kill(self.other_processes.get(), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def get_file_items(self, window, files):
        # create set of each mime type
        all_exts = set()
        number_exts = 0
        ext_type = None
        for file in files:
            ext_type = get_file_ext(file)
            if (not ext_type) or (ext_type not in ACCEPTED_EXTENSIONS):
                return
            if ext_type not in all_exts:
                number_exts += 1
                all_exts.add(ext_type)
        
        if not all_exts:
            return

        valid_group = []
        for converter in SOX_CONVERTER_LIST:
            if all_exts <= set(converter['ext_type']):
                valid_group.append(converter)

        if not valid_group:
            return


        top_menuitem = Nautilus.MenuItem(name='SoxMenuProvider::SoxConverter', 
                                         label='SoxConverter...', 
                                         tip='',
                                         icon='')
        submenu = Nautilus.Menu()
        top_menuitem.set_submenu(submenu)

        for converter in valid_group:
            sub_menuitem = Nautilus.MenuItem(
                name='SoxMenuProvider::' + converter['label'],
                label=converter['label'], tip='', icon='')
            sub_menuitem.connect('activate', self.on_click, files, converter)
            submenu.append_item(sub_menuitem)

        # print(f"-------------all_exts:{all_exts}")
        # print(f"---------------------label:{converter['label']}")
        # print(f"---------------------valid_group:{valid_group}")

        return top_menuitem,

    def on_click(self, menu, files, convert_type):
        # create progress bar
        progressbar = self.__create_progressbar()
        progressbar.set_text("Converting")
        progressbar.set_pulse_step = 1.0 / len(files)
        self.infobar.show_all()

        processing_queue = mp.Queue()

        self.process = mp.Process(target=self.__convert_files,
                                  args=(files, convert_type, processing_queue))
        self.process.daemon = True
        self.process.start()

        GLib.timeout_add(100, self.__update_progressbar, processing_queue, progressbar)

    def __convert_files(self, files, convert_type, processing_queue):
        for file in files:
            in_ext_type = get_file_ext(file)
            if not in_ext_type:
                continue
            in_uri = unquote(file.get_uri()[7:])
            if convert_type['label'] == 'raw':
                out_ext_type = 'raw'
            else:
                out_ext_type = 'wav'
            
            suffix = convert_type['suffix']
            
            out_uri = find_uri_not_in_use(change_uri(in_uri, suffix, out_ext_type))

            if in_ext_type == 'raw' or in_ext_type == 'pcm':
                gopts = ''
                ifopts = f"{convert_type['param']['ofopts']} -t raw"
                ofopts = ''
            else:
                gopts = convert_type['param']['gopts']
                ifopts = convert_type['param']['ifopts']
                ofopts = convert_type['param']['ofopts']

            # raw2wav
            # sox -r 16000 -c 1 -e signed-integer -b 16 -t raw 3.pcm 3.wav

            # wav2wav
            # sox in.wav -r 48000 -c 1 -e signed-integer -b 16 out.wav

            # wav2raw
            # sox --magic in.wav -t raw out.raw
            process = subprocess.Popen(f"exec sox {gopts} {ifopts} '{in_uri}' {ofopts} '{out_uri}'", shell=True)
            self.other_processes.put(process.pid)
            process.wait()
            self.other_processes.get()
            processing_queue.put(file.get_name())
        processing_queue.put(None)
        return True

    def __create_progressbar(self) -> Gtk.ProgressBar:
        """ Create the progressbar used to notify that files are currently
        being processed.
        """
        self.infobar.set_show_close_button(True)
        self.infobar.set_message_type(Gtk.MessageType.INFO)
        self.infobar_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        progressbar = Gtk.ProgressBar()
        self.infobar_hbox.pack_start(progressbar, True, True, 0)
        progressbar.set_show_text(True)

        self.infobar.get_content_area().pack_start(self.infobar_hbox, True, True, 0)
        self.infobar.show_all()

        return progressbar

    def __update_progressbar(self, processing_queue, progressbar) -> bool:
        if not processing_queue.empty():
            fname = processing_queue.get(block=False)
        else:
            return True

        if fname is None:
            self.infobar_hbox.destroy()
            self.infobar.hide()
            if not processing_queue.empty():
                print("Something went wrong, the queue isn't empty :/")
            return False

        progressbar.pulse()
        progressbar.set_text(f"Converting {fname}")
        progressbar.show_all()
        self.infobar_hbox.show_all()
        self.infobar.show_all()
        return True

    def get_background_items(self, window, files):
        return None
