import 'package:flutter/material.dart';

class AppTheme {
  static const Color background = Color(0xff111827);

  static const Color sidebar = Color(0xff17233A);

  static const Color card = Color(0xff1E2D49);

  static const Color card2 = Color(0xff263A5A);

  static const Color accent = Color(0xff4D7CFE);

  static const Color success = Color(0xff16C784);

  static const Color warning = Color(0xffF4B400);

  static const Color danger = Color(0xffEA4335);

  static const Color textPrimary = Colors.white;

  static const Color textSecondary = Color(0xffA5B4C7);

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,

      useMaterial3: true,

      scaffoldBackgroundColor: background,

      fontFamily: "Roboto",

      colorScheme: const ColorScheme.dark(
        surface: card,
        primary: accent,
        secondary: accent,
      ),

      appBarTheme: const AppBarTheme(
        backgroundColor: sidebar,
        elevation: 0,
        centerTitle: false,
        foregroundColor: Colors.white,
      ),

      cardTheme: CardThemeData(
        color: card,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: card,

        hintStyle: const TextStyle(
          color: textSecondary,
        ),

        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: BorderSide.none,
        ),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: BorderSide.none,
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(15),
          borderSide: const BorderSide(
            color: accent,
            width: 1.2,
          ),
        ),
      ),

      iconTheme: const IconThemeData(
        color: Colors.white,
      ),

      dividerColor: Colors.white10,

      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          color: textPrimary,
          fontSize: 30,
          fontWeight: FontWeight.bold,
        ),

        headlineMedium: TextStyle(
          color: textPrimary,
          fontSize: 24,
          fontWeight: FontWeight.w600,
        ),

        titleLarge: TextStyle(
          color: textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w600,
        ),

        titleMedium: TextStyle(
          color: textPrimary,
          fontSize: 16,
        ),

        bodyLarge: TextStyle(
          color: textPrimary,
          fontSize: 15,
        ),

        bodyMedium: TextStyle(
          color: textSecondary,
          fontSize: 14,
        ),

        labelLarge: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w600,
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: accent,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          padding: const EdgeInsets.symmetric(
            horizontal: 20,
            vertical: 16,
          ),
        ),
      ),

      floatingActionButtonTheme: const FloatingActionButtonThemeData(
        backgroundColor: accent,
        foregroundColor: Colors.white,
      ),

      scrollbarTheme: ScrollbarThemeData(
        thumbColor: WidgetStateProperty.all(accent.withValues(alpha: .7)),
        radius: const Radius.circular(20),
      ),
    );
  }
}
