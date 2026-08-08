;;; foo-core.el --- Sample CGC Emacs Lisp fixture -*- lexical-binding: t; -*-

;;; Commentary:
;; This file exercises common Emacs Lisp definition forms for parser tests.

;;; Code:

(require 'cl-lib)

(defvar foo-core-count 0
  "Number of greetings produced.")

(defconst foo-core-default-name "Neo"
  "Default user name.")

(defcustom foo-core-loud nil
  "Whether greetings should be loud."
  :type 'boolean
  :group 'foo-core)

(defun foo-core-format (name &optional loud)
  "Build a greeting for NAME.
When LOUD is non-nil, uppercase the greeting."
  (let ((greeting (format "Hello, %s" name)))
    (if loud
        (upcase greeting)
      greeting)))

(defsubst foo-core-increment (value)
  "Increment VALUE."
  (1+ value))

(defmacro foo-core-with-name (name &rest body)
  "Bind NAME around BODY."
  `(let ((current-name ,name))
     ,@body))

(cl-defun foo-core-greet (&key (name foo-core-default-name) loud)
  "Return a greeting using keyword arguments."
  (setq foo-core-count (foo-core-increment foo-core-count))
  (foo-core-format name loud))

(provide 'foo-core)
;;; foo-core.el ends here
