#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <string.h>
#include <sched.h>
#include <sys/mman.h>
#include <gpiod.h>

#define UART_DEVICE "/dev/ttyAMA0"
#define BAUDRATE 921600

#define GPIO_CHIP "/dev/gpiochip0"
#define GPIO_LINE 23

int setup_uart()
{
    int fd = open(UART_DEVICE, O_RDWR | O_NOCTTY | O_SYNC);

    struct termios tty;
    tcgetattr(fd, &tty);

    cfsetospeed(&tty, BAUDRATE);
    cfsetispeed(&tty, BAUDRATE);

    tty.c_cflag = (tty.c_cflag & ~CSIZE) | CS8;
    tty.c_cflag |= (CLOCAL | CREAD);
    tty.c_cflag &= ~(PARENB | PARODD | CSTOPB | CRTSCTS);

    tty.c_iflag = 0;
    tty.c_oflag = 0;
    tty.c_lflag = 0;

    tcsetattr(fd, TCSANOW, &tty);

    return fd;
}

int main()
{
    mlockall(MCL_CURRENT | MCL_FUTURE);

    struct sched_param sp = { .sched_priority = 80 };
    sched_setscheduler(0, SCHED_FIFO, &sp);

    int uart = setup_uart();
    if (uart < 0) return 1;

    struct gpiod_chip *chip = gpiod_chip_open(GPIO_CHIP);

    struct gpiod_line_settings *settings = gpiod_line_settings_new();
    gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_INPUT);
    gpiod_line_settings_set_edge_detection(
        settings, GPIOD_LINE_EDGE_RISING);

    struct gpiod_line_config *line_cfg = gpiod_line_config_new();
    unsigned int offset = GPIO_LINE;
    gpiod_line_config_add_line_settings(line_cfg, &offset, 1, settings);

    struct gpiod_request_config *req_cfg = gpiod_request_config_new();
    gpiod_request_config_set_consumer(req_cfg, "pulse_uart_tx");

    struct gpiod_line_request *request =
        gpiod_chip_request_lines(chip, req_cfg, line_cfg);

    struct gpiod_edge_event_buffer *buffer =
        gpiod_edge_event_buffer_new(32);

    uint8_t value = 0;

    while (1)
    {
        if (gpiod_line_request_wait_edge_events(request, -1) > 0)
        {
            int events =
                gpiod_line_request_read_edge_events(request, buffer, 32);

            for (int i = 0; i < events; i++)
            {
                uint32_t word = 0x01010101u * value;
                write(uart, &word, 4);
                value++;
            }
        }
    }

    return 0;
}