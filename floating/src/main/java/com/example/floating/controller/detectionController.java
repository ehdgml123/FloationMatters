package com.example.floating.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

@Controller
public class detectionController {

     @GetMapping(value = "/detection")
    public String detection() {

         return "detection";
     }


}
