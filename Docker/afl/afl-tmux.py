#! /usr/bin/python

import argparse
import os
import libtmux
import math
import yaml


def create_parser():
    # TODO добавить распараллеливание на разных хостах
    # TODO не отображаются русские символы в сессии tmux докера
    # TODO добавить в yaml настройку своих параметров afl (например qemu mod)
    # TODO дополнить tmux.conf
    # TODO продумать логику, как запускать разные цели
    # TODO добавить персональные настройки для экземпляров (например вдруг для санитайзера нужны другие аргументы цели)
    # TODO или ограничение памяти afl (например для lsan)
    # TODO подумать как отчищать метрики для старых запусков и нужно ли вообще
    new_parser = argparse.ArgumentParser(
        prog='AFL tmux',
        description='Запускает выбранные цели для фаззинга в параллельном режиме и строит графики '
                    'в Grafana',
        epilog='Text at the bottom of help')

    new_parser.add_argument('config', type=str,
                            help='Путь к конфигурационному yml файлу')
    new_parser.add_argument('-i', '--interactive', dest='is_interactive', action='store_true',
                            help='Включает интерактивный режим выбора кол-во экземпляров')
    new_parser.add_argument('-f', '--force', dest='is_force', action='store_true',
                            help='Принудительно запустить указанное кол-во экземпляров без проверки на доступные ядра')

    return new_parser


def create_tmux_windows(used_threads, commands):
    server_tmux = libtmux.Server()
    print(server_tmux)
    # TODO: проверить создан ли сервер
    session = server_tmux.new_session()

    used_threads = config['used_threads']
    windows = math.ceil(used_threads / 4)
    panes_amount = used_threads
    print(windows)
    # TODO: вывести на нулевом окне команду afl-whatsup и не вводить

    for i in range(windows):
        window_name = '{} to {} fuzzers'.format((i * 4) + 1, (i * 4) + 4)
        curr_win = session.new_window(attach=False, window_name=window_name)
        curr_win.split_window(attach=False, vertical=False)

        # TODO поменять местами панельки (сейчас первая панель правая сверху, должна быть левая)
        pane1 = curr_win.select_pane('-R')
        pane2 = curr_win.select_pane('-L')
        pane3 = pane1.split_window(attach=False)
        pane4 = pane2.split_window(attach=False)

        panes = [pane1, pane2, pane3, pane4]
        for pane in panes:
            if used_threads - panes_amount < len(commands):
                pane.send_keys(commands[used_threads - panes_amount], enter=True)
                panes_amount -= 1


def get_amount_fuzzers(builds):
    out = os.popen('afl-gotcpu').read()
    template = '\n'.join(out.split('\n')[:2]) + '\n'
    print(out.replace(template, ''), end='')

    av_cores = out.count('AVAILABLE') + out.count('CAUTION')
    print('Найдено файлов для параллельного запуска: ' + str(builds))
    print('Доступно ядер: ' + str(av_cores))

    nonsan_threads = 0
    if builds > av_cores:
        print('ОШИБКА: Освободите ядра или уменьшите кол-во выбранных файлов для параллельного запуска.')
        exit()
    if builds < av_cores:
        print('Можно запустить несколько экземпляров (' + str(av_cores - builds) + ')'
              + ' программы без санитайзеров, выберите кол-во от 1 до ' + str(av_cores - builds))

        nonsan_threads = int(input())
        if nonsan_threads == 0:
            # TODO ну ваще та нет
            print('ОШИБКА: должен быть хотя бы один экземпляр фаззера без санитайзеров')
            exit()
        elif nonsan_threads > av_cores - builds:
            print('ОШИБКА: вы выбрали недоступное кол-во ядер')
            exit()

    threads = builds + nonsan_threads
    print('Будет запущено ' + str(threads) + ' экземпляров фаззера')
    return threads, nonsan_threads


def get_fuzzer_commands(config):
    commands = []

    cmd = '{env} afl-fuzz -S {name} -T {name} -i {in} -o {out} -- {path} {args}'
    cmd_format = {
        'env': ' '.join(config['fuzzer_settings']['afl_environment']),
        'in': config['fuzzer_settings']['input_dir'],
        'out': config['fuzzer_settings']['output_dir'],
        'args': config['fuzzer_settings']['arguments']
    }

    targets = config['targets']
    i = 0
    for target in targets:
        for t in range(targets[target]['threads']):
            i += 1
            cmd_format['name'] = target + '-' + str(i)
            cmd_format['path'] = targets[target]['path']
            commands.append(cmd.format(**cmd_format))

    # Один из экземпляров должен быть мастером
    commands[0] = commands[0].replace('-S', '-M')

    return commands


def get_config(config_path):
    with open(config_path, 'r') as stream:
        config_data = yaml.safe_load(stream)

    targets = config_data['targets']
    used_threads = 0
    for target in targets:
        used_threads += targets[target]['threads']
    config_data['used_threads'] = used_threads

    return config_data


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()
    print(args)

    config = get_config(args.config)
    print(config)

    if args.is_interactive:
        pass

    if args.is_force:
        pass

    afl_commands = get_fuzzer_commands(config)
    print(afl_commands)

    create_tmux_windows(config['used_threads'], afl_commands)
