;;; foo-ui.el --- Sample CGC Emacs Lisp caller fixture -*- lexical-binding: t; -*-

;;; Commentary:
;; This file requires foo-core and calls its direct functions.

;;; Code:

(require 'foo-core)

(autoload 'foo-ui-autoloaded "foo-ui-autoloaded" "Autoloaded command." t)

(defun foo-ui-render (name)
  "Render a greeting for NAME."
  (message "%s" (foo-core-greet :name name))
  (funcall #'foo-ui-after-render name)
  (apply #'foo-ui-log (list name)))

(defun foo-ui-after-render (name)
  "Hook run after rendering NAME."
  (message "Rendered %s" name))

(provide 'foo-ui)
;;; foo-ui.el ends here
