#define _FILE_OFFSET_BITS 64

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define SLCR_UNLOCK 0xF8000008ULL
#define SLCR_LOCK 0xF8000004ULL
#define APER_CLK_CTRL 0xF800012CULL
#define MIO_PIN_28 0xF8000770ULL
#define MIO_PIN_46 0xF80007B8ULL
#define GPIO_MASK_DATA_1_LSW 0xE000A008ULL
#define GPIO_DIRM_1 0xE000A244ULL
#define GPIO_OEN_1 0xE000A248ULL
#define USB_RESET_BIT (1U << 14)

static int mem_fd = -1;
static long page_size;

static volatile uint32_t *map_reg(uint64_t address, void **mapping) {
    uint64_t page = address & ~((uint64_t)page_size - 1);
    size_t offset = (size_t)(address - page);
    *mapping = mmap(NULL, (size_t)page_size, PROT_READ | PROT_WRITE,
                    MAP_SHARED, mem_fd, (off_t)page);
    if (*mapping == MAP_FAILED)
        return NULL;
    return (volatile uint32_t *)((unsigned char *)*mapping + offset);
}

static int write_reg(uint64_t address, uint32_t value) {
    void *mapping;
    volatile uint32_t *reg = map_reg(address, &mapping);
    if (!reg) {
        fprintf(stderr, "mmap 0x%08llx failed: %s\n",
                (unsigned long long)address, strerror(errno));
        return -1;
    }
    *reg = value;
    __sync_synchronize();
    munmap(mapping, (size_t)page_size);
    return 0;
}

static int mask_write(uint64_t address, uint32_t mask, uint32_t value) {
    void *mapping;
    volatile uint32_t *reg = map_reg(address, &mapping);
    uint32_t current;
    if (!reg) {
        fprintf(stderr, "mmap 0x%08llx failed: %s\n",
                (unsigned long long)address, strerror(errno));
        return -1;
    }
    current = *reg;
    *reg = (current & ~mask) | (value & mask);
    __sync_synchronize();
    printf("0x%08llx: 0x%08x -> 0x%08x\n",
           (unsigned long long)address, current, *reg);
    munmap(mapping, (size_t)page_size);
    return 0;
}

int main(void) {
    static const uint32_t usb_mio_values[12] = {
        0x00000304, 0x00000305, 0x00000304, 0x00000305,
        0x00000304, 0x00000304, 0x00000304, 0x00000304,
        0x00000305, 0x00000304, 0x00000304, 0x00000304,
    };
    unsigned int index;

    page_size = sysconf(_SC_PAGESIZE);
    mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (page_size <= 0 || mem_fd < 0) {
        perror("open /dev/mem");
        return 1;
    }

    if (write_reg(SLCR_UNLOCK, 0x0000DF0D))
        return 1;
    if (mask_write(APER_CLK_CTRL, (1U << 22) | (1U << 2),
                   (1U << 22) | (1U << 2)))
        return 1;
    for (index = 0; index < 12; ++index) {
        if (mask_write(MIO_PIN_28 + 4ULL * index, 0x00003FFF,
                       usb_mio_values[index]))
            return 1;
    }
    if (mask_write(MIO_PIN_46, 0x00003FFF, 0x00001200) ||
        mask_write(GPIO_DIRM_1, USB_RESET_BIT, USB_RESET_BIT) ||
        mask_write(GPIO_OEN_1, USB_RESET_BIT, USB_RESET_BIT))
        return 1;

    if (write_reg(GPIO_MASK_DATA_1_LSW, 0xBFFF0000))
        return 1;
    usleep(50000);
    if (write_reg(GPIO_MASK_DATA_1_LSW, 0xBFFF4000))
        return 1;
    usleep(1000);
    if (mask_write(GPIO_OEN_1, USB_RESET_BIT, 0) ||
        mask_write(GPIO_DIRM_1, USB_RESET_BIT, 0) ||
        mask_write(MIO_PIN_46, 0x00003FFF, 0x00001201))
        return 1;
    usleep(200000);
    if (write_reg(SLCR_LOCK, 0x0000767B))
        return 1;

    close(mem_fd);
    puts("USB0 ULPI MIO configured; USB3320 reset pulse complete.");
    return 0;
}
