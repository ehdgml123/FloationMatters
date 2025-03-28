package com.example.floating.controller;

import lombok.extern.log4j.Log4j;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
@Log4j
public class DstatisticsController {

    @GetMapping(value = "/dstatistics")
    public String Dstatistics() {
        return "Detectionstatistics";
    }
}
