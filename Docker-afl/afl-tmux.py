#! /usr/bin/python

import argparse
import os
import libtmux
import math

# "-r \"unserialize(file_get_contents("php://stdin'));\""
def init_parser():
    parser = argparse.ArgumentParser(description='Great Description To Be Here')

    # TODO in out
    # TODO добвить режим
    # TODO force режим, что бы запускать на переполненных ядрах
    # TODO добавить инфу об statsd port и host
    # TODO флаг для завершения всех фаззеров (без закрытия сессии, что бы можно было чекнуть результаты)
    parser.add_argument('-b', '--builds', dest='path_to_builds', type=str)
    parser.add_argument('-a', '--args', dest="args", type=str)

    return parser


def create_tmux_windows(threads, commands):
    server_tmux = libtmux.Server()
    print(server_tmux)
    # TODO: проверить создан ли сервер
    session = server_tmux.new_session()

    windows = math.ceil(threads / 4)
    panes_amount = threads
    print(windows)
    # TODO: вывести на нулевом окне коммануду afl-gotcpu и не вводить

    for i in range(windows):
        window_name = "{} to {} fuzzers".format((i * 4) + 1, (i * 4) + 4)
        curr_win = session.new_window(attach=False, window_name=window_name)
        curr_win.split_window(attach=False, vertical=False)

        pane1 = curr_win.select_pane("-L")
        pane2 = curr_win.select_pane("-R")
        pane3 = pane1.split_window(attach=False)
        pane4 = pane2.split_window(attach=False)

        panes = [pane1, pane2, pane3, pane4]
        for pane in panes:
            if threads - panes_amount < len(commands):
                pane.send_keys(commands[threads - panes_amount], enter=True)
                panes_amount -= 1


def parse_dir(path_to_builds):
    dir, __, files = next(os.walk(path_to_builds))

    if "default" not in files:
        print("ERROR not default")
        exit()

    if len(files) == 0:
        print("ОШИБКА: директория с файлами для запуска пуста")
        exit()

    return files


def get_amount_fuzzers(builds):
    out = os.popen('afl-gotcpu').read()
    template = "\n".join(out.split("\n")[:2]) + "\n"
    print(template)
    print(out.replace(template, ""), end='')

    av_cores = out.count("AVAILABLE") + out.count("CAUTION")
    print("Найдено файлов для параллельного запуска: " + str(builds))
    print("Доступно ядер: " + str(av_cores))

    nonsan_threads = 0
    if builds > av_cores:
        print("ОШИБКА: Освободите ядра или уменьшите кол-во выбранных файлов для параллельного запуска.")
        exit()
    if builds < av_cores:
        print("Можно запустить несколько экземпляров (" + str(av_cores - builds) + ")"
              + " программы без санитайзеров, выберите кол-во от 1 до " + str(av_cores - builds))

        nonsan_threads = int(input())
        if nonsan_threads == 0:
            # TODO ну ваще та нет
            print("ОШИБКА: должен быть хотя бы один экземпляр фаззера без санитайзеров")
            exit()
        elif nonsan_threads > av_cores - builds:
            print("ОШИБКА: вы выбрали недоступное кол-во ядер")
            exit()

    threads = builds + nonsan_threads
    print("Будет запущено " + str(threads) + " экземпляров фаззера")
    return threads, nonsan_threads


def generate_fuzzer_cmds(files, nonsan_threads, args):
    commands = []

    cmd_args = {
        'name': files[0] + "-1",
        'file': "./" + os.path.join(args.path_to_builds, files[0]),
        'args': args.args
    }

    global_env = "AFL_STATSD_TAGS_FLAVOR=dogstatsd AFL_STATSD=1 AFL_STATSD_HOST=statsd_exporter AFL_STATSD_PORT=9125"
    master_cmd = global_env + " afl-fuzz -M {name} -T {name} -i in -o out -- {file} {args}"
    commands.append(master_cmd.format(**cmd_args))

    slave_cmd = global_env + " afl-fuzz -S {name} -T {name} -i in -o out -- {file} {args}"
    for i in range(1, len(files)):
        cmd_args['file'] = "./" + os.path.join(args.path_to_builds, files[i])
        cmd_args['name'] = files[i] + "-" + str(i + 1)
        commands.append(slave_cmd.format(**cmd_args))

    if "default" in files:
        for i in range(nonsan_threads):
            cmd_args['name'] = "default-" + str(len(files) + i + 1)
            cmd_args['file'] = "./" + os.path.join(args.path_to_builds, "default")
            commands.append(slave_cmd.format(**cmd_args))

    for e in commands:
        print(e)

    return commands


if __name__ == "__main__":
    parser = init_parser()
    args = parser.parse_args()
    print(args)

    files = parse_dir(args.path_to_builds)
    threads, nonsan_threads = get_amount_fuzzers(len(files))
    print(threads, nonsan_threads)

    commands = generate_fuzzer_cmds(files, nonsan_threads, args)

    create_tmux_windows(threads, commands)
