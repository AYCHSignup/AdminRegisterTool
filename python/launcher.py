#!/usr/bin/env python

# Python 3 required. A virtualenv is recommended. Install requirements.txt.

import datetime
import locale
import os
import queue
import threading
import time
import tkinter as tk
import traceback

import art_student_loader


try:
    import settings_secret as settings
except:
    import settings_default as settings
    print("*** USING DEFAULTS in settings_default.py.")
    print("*** Please copy settings_default.py to settings_secret.py and modify that!")

locale.setlocale(locale.LC_ALL, 'en_US')

STATE_IDLE = "IDLE"
STATE_DOWN = "DOWNLOADING"
STATE_UP = "UPLOADING"


class MTListbox(tk.Listbox):
    def __init__(self, master, **options):
        tk.Listbox.__init__(self, master, **options)
        self.queue = queue.Queue()
        self.update_me()

    def write(self, line):
        self.queue.put(line)

    def clear(self):
        self.queue.put(None)

    def update_me(self):
        try:
            while True:
                line = self.queue.get_nowait()
                if line is None:
                    self.delete(0, tk.END)
                else:
                    self.insert(tk.END, str(line))
                self.see(tk.END)
                self.update_idletasks()
        except queue.Empty:
            pass
        self.after(100, self.update_me)


class App:

    def __init__(self, master):
        self.downloader_thread = None
        self.setup_main_frame(master)
        self.setup_sftp_frame(master)
        self.setup_art_frame(master)

    def set_downloader_status(self, message):
        self.downloader_status.clear()
        self.downloader_status.write(message)

    def progress(self, message, bytes_written=None, bytes_remaining=None):
        if message is not None:
            self.downloader_output.write(message)
        else:
            self.set_downloader_status("DOWNLOADING: %d of %d bytes written" % (bytes_written, bytes_remaining))

    def check_file(self):
        try:
            st = os.stat(self.localfile.get())
            writable = os.access(self.localfile.get(), os.W_OK)
            self.check_file_label['text'] = "File '%s' found, size %s bytes. %s" % (
                self.localfile.get(), locale.format('%d', st.st_size, grouping=True),
                "Writable." if writable else "FILE IS NOT WRITABLE!!")
        except FileNotFoundError:
            self.check_file_label['text'] = "File '%s' not found. It will be created." % self.localfile.get()
        except:
            self.check_file_label['text'] = "Can't access file '%s'! Permission problem?" % self.localfile.get()

    def test_art_connection(self):
        self.art_test_label["text"] = "Checking ART REST endpoint... (TODO)"

    def test_sftp_connection(self):
        self.sftp_test_label["text"] = "Looking for remote file... (TODO)"

    def go(self):
        if self.downloader_thread and self.downloader_thread.is_alive():
            self.downloader_output.write("Downloader thread running - can't start!")
            return

        self.downloader_thread = threading.Thread(target=self.download_callable, name="downloader", daemon=True)
        self.downloader_thread.start()

    def download_callable(self):
        success = False
        self.set_downloader_status(STATE_DOWN)
        self.downloader_output.clear()

        self.downloader_output.write("WORK STARTED at %s" % datetime.datetime.now())
        try:
            success = art_student_loader.download_student_csv(
                hostname=self.sftp_host.get(),
                port=settings.SFTP_PORT,
                username=self.sftp_user.get(),
                password=self.sftp_password.get(),
                keyfile=settings.SFTP_KEYFILE,
                keypass=settings.SFTP_KEYPASS,
                remotepath=self.sftp_file.get(),
                localfile=self.localfile.get(),
                offset=None,
                progress=self.progress)
        except Exception as e:
            self.downloader_output.write("Encountered exception: %s" % e)
            traceback.print_exc()

        if success:
            self.set_downloader_status(STATE_UP)
            self.downloader_output.write("STARTING UPLOAD at %s" % datetime.datetime.now())
            try:
                art_student_loader.load_student_data(
                    filename=self.localfile.get(),
                    encoding=None,
                    delimiter=None,
                    csv_start_line=None,
                    num_students=None,
                    dry_run=False,
                    endpoint=self.art_endpoint.get(),
                    username=self.art_user.get(),
                    password=self.art_password.get(),
                    progress=self.progress)
            except Exception as e:
                self.downloader_output.write("Encountered exception: %s" % e)
                traceback.print_exc()

        self.downloader_output.write("WORK ENDED at %s\n\n" % datetime.datetime.now())
        self.set_downloader_status(STATE_IDLE)

    def setup_main_frame(self, master):

        main_frame = tk.LabelFrame(master, text="Main", padx=10, pady=5)
        main_frame.grid(row=0, sticky=tk.W + tk.E, padx=10, pady=5)

        tk.Label(main_frame, text="Local filename").grid(row=10, sticky=tk.W)
        self.localfile = tk.StringVar()
        self.localfile.set(
            art_student_loader.datewise_filepath(
                None,
                settings.SFTP_FILE_BASENAME,
                settings.SFTP_FILE_DATEFORMAT,
                settings.SFTP_FILE_EXT))
        tk.Entry(main_frame, textvariable=self.localfile).grid(row=10, column=1, sticky=tk.W + tk.E)

        tk.Button(main_frame, text="Check File Details", command=self.check_file).grid(row=20, sticky=tk.W)
        self.check_file_label = tk.Label(main_frame, relief=tk.GROOVE, text="<-- press to check file", anchor=tk.W)
        self.check_file_label.grid(row=20, column=1, sticky=tk.W + tk.E)

        tk.Label(main_frame, text="").grid(row=21, sticky=tk.W)
        tk.Button(main_frame, text="GO!", command=self.go).grid(row=22, sticky=tk.W)

        tk.Label(main_frame, text="").grid(row=24, sticky=tk.W)

        tk.Label(main_frame, text="Status").grid(row=25, sticky=tk.W)
        self.downloader_status = MTListbox(main_frame, width=40, height=1)
        self.downloader_status.grid(row=25, column=1, sticky=tk.W + tk.E)
        self.set_downloader_status(STATE_IDLE)

        tk.Label(main_frame, text="Output").grid(row=29, sticky=tk.W)
        self.downloader_output = MTListbox(main_frame, width=80, height=15, selectmode=tk.EXTENDED)
        self.downloader_output.grid(row=30, column=0, columnspan=2)
        self.scrollY = tk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.downloader_output.yview)
        self.scrollY.grid(row=30, column=2, sticky=tk.N + tk.S)
        self.scrollX = tk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.downloader_output.xview)
        self.scrollX.grid(row=40, column=0, columnspan=2, sticky=tk.W + tk.E)
        self.downloader_output['xscrollcommand'] = self.scrollX.set
        self.downloader_output['yscrollcommand'] = self.scrollY.set
        tk.Button(main_frame, text="Clear", command=self.downloader_output.clear).grid(row=29, column=1, sticky=tk.E)

    def setup_sftp_frame(self, master):

        sftp_frame = tk.LabelFrame(master, text="sFTP Settings", padx=10, pady=5)
        sftp_frame.grid(row=1, sticky=tk.W + tk.E, padx=10, pady=5)

        tk.Label(sftp_frame, text="File Path").grid(row=0, sticky=tk.W)
        self.sftp_file = tk.StringVar()
        self.sftp_file.set(
            art_student_loader.datewise_filepath(
                settings.SFTP_FILE_DIR,
                settings.SFTP_FILE_BASENAME,
                settings.SFTP_FILE_DATEFORMAT,
                settings.SFTP_FILE_EXT))
        tk.Entry(sftp_frame, textvariable=self.sftp_file).grid(row=0, column=1, sticky=tk.W + tk.E)

        tk.Label(sftp_frame, text="Hostname").grid(row=1, sticky=tk.W)
        self.sftp_host = tk.StringVar()
        self.sftp_host.set(settings.SFTP_HOSTNAME)
        tk.Entry(sftp_frame, textvariable=self.sftp_host).grid(row=1, column=1, sticky=tk.W + tk.E)

        tk.Label(sftp_frame, text="Username").grid(row=2, sticky=tk.W)
        self.sftp_user = tk.StringVar()
        self.sftp_user.set(settings.SFTP_USER)
        tk.Entry(sftp_frame, textvariable=self.sftp_user).grid(row=2, column=1, sticky=tk.W + tk.E)

        tk.Label(sftp_frame, text="Password").grid(row=3, sticky=tk.W)
        self.sftp_password = tk.StringVar()
        self.sftp_password.set(settings.SFTP_PASSWORD)
        tk.Entry(sftp_frame, textvariable=self.sftp_password, show='*').grid(row=3, column=1, sticky=tk.W + tk.E)

        # tk.Button(sftp_frame, text="Test sFTP Connection", command=self.test_sftp_connection).grid(row=4)
        # self.sftp_test_label = tk.Label(
        #     sftp_frame, relief=tk.GROOVE, text="<-- press to check for file on sFTP host", anchor=tk.W)
        # self.sftp_test_label.grid(row=4, column=1, sticky=tk.W + tk.E)

    def setup_art_frame(self, master):

        art_frame = tk.LabelFrame(master, text="ART REST API Settings", padx=10, pady=5)
        art_frame.grid(row=2, sticky=tk.W + tk.E, padx=10, pady=10)

        tk.Label(art_frame, text="Endpoint").grid(row=7, sticky=tk.W)
        self.art_endpoint = tk.StringVar()
        self.art_endpoint.set(settings.ART_ENDPOINT)
        tk.Entry(art_frame, textvariable=self.art_endpoint).grid(row=7, column=1, sticky=tk.W + tk.E)

        tk.Label(art_frame, text="Username").grid(row=8, sticky=tk.W)
        self.art_user = tk.StringVar()
        self.art_user.set(settings.AUTH_PAYLOAD.get('username', ''))
        tk.Entry(art_frame, textvariable=self.art_user).grid(row=8, column=1, sticky=tk.W + tk.E)

        tk.Label(art_frame, text="Password").grid(row=9, sticky=tk.W)
        self.art_password = tk.StringVar()
        self.art_password.set(settings.AUTH_PAYLOAD.get('password', ''))
        tk.Entry(art_frame, textvariable=self.art_password, show='*').grid(row=9, column=1, sticky=tk.W + tk.E)

        # tk.Button(art_frame, text="Test ART Connection", command=self.test_art_connection).grid(row=10)
        # self.art_test_label = tk.Label(
        #     art_frame, relief=tk.GROOVE, text="<-- press to check ART REST API connection", anchor=tk.W)
        # self.art_test_label.grid(row=10, column=1, sticky=tk.W + tk.E)


root = tk.Tk()

app = App(root)

root.mainloop()
